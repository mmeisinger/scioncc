#!/usr/bin/env python

"""Web UI providing development views and actions"""

__author__ = 'Michael Meisinger'

import collections, traceback, datetime, time, yaml
import flask, ast, pprint
from flask import Flask, request, abort
from gevent.wsgi import WSGIServer
import json

from pyon.core.object import IonObjectBase
from pyon.core.registry import getextends, model_classes
from pyon.public import Container, StandaloneProcess, log, PRED, RT, IonObject, CFG, NotFound, Inconsistent, BadRequest, Unauthorized, named_any

from interface import objects


# Initialize the flask app - abs path so that static files can be loaded from egg
app = Flask(__name__)

DEFAULT_WEB_SERVER_HOSTNAME = "localhost"
DEFAULT_WEB_SERVER_PORT = 8080

adminui_instance = None

standard_types = ['str', 'int', 'bool', 'float', 'list', 'dict']
standard_resattrs = ['name', 'description', 'lcstate', 'availability', 'visibility', 'ts_created', 'ts_updated', 'alt_ids']
EDIT_IGNORE_FIELDS = ['rid', 'restype', 'lcstate', 'availability', 'visibility', 'ts_created', 'ts_updated']
EDIT_IGNORE_TYPES = ['list', 'dict', 'bool']
standard_eventattrs = ['origin', 'ts_created', 'description']
date_fieldnames = ['ts_created', 'ts_updated']

CFG_PREFIX = "process.admin_ui"


class AdminUI(StandaloneProcess):
    """
    A simple Web UI to introspect the container and the ION datastores.
    """
    def on_init(self):

        self.http_server = None
        self.server_hostname = self.CFG.get_safe(CFG_PREFIX + '.web_server.hostname', DEFAULT_WEB_SERVER_HOSTNAME)
        self.server_port = self.CFG.get_safe(CFG_PREFIX + '.web_server.port', DEFAULT_WEB_SERVER_PORT)
        self.web_server_enabled = True
        self.logging = None
        self.interaction_observer = None
        app.secret_key = self.__class__.__name__   # Enables sessions (for mscweb)

        #retain a pointer to this object for use in ProcessRPC calls
        global adminui_instance
        adminui_instance = self

        #Start the gevent web server unless disabled
        if self.web_server_enabled:
            self.start_service(self.server_hostname, self.server_port)

    def on_quit(self):
        if self.interaction_observer and self.interaction_observer.started:
            self.interaction_observer.stop()
        self.stop_service()

    def start_service(self, hostname=DEFAULT_WEB_SERVER_HOSTNAME, port=DEFAULT_WEB_SERVER_PORT):
        """Responsible for starting the gevent based web server."""
        if self.http_server is not None:
            self.stop_service()

        self.http_server = WSGIServer((hostname, port), app, log=self.logging)
        self.http_server.start()
        return True

    def stop_service(self):
        """Responsible for stopping the gevent based web server."""
        if self.http_server is not None:
            self.http_server.stop()
        return True


# ----------------------------------------------------------------------------------------

def _get_resmenu_extension():
    resmenu_ext = CFG.get_safe(CFG_PREFIX + '.menu.extensions')
    if not resmenu_ext:
        return ""
    ext_str = ""
    for ext in resmenu_ext:
        if isinstance(ext, basestring):
            ext = ext.split(",")
        ext_str += "<li>%s: %s</li>\n" % (ext[0], ", ".join("<a href='/list/%s'>%s</a>" % (rex, rex) for rex in ext[1:]))
    return ext_str

@app.route('/', methods=['GET', 'POST'])
def process_index():
    try:
        from pyon.public import CFG
        from pyon.core.bootstrap import get_sys_name
        default_ds_server = CFG.get_safe("container.datastore.default_server", "postgresql")



        fragments = [
            "<h1>SciON Admin UI</h1>",
            "<p><ul>",
            "<li><a href='/restypes'><b>Browse Resource Registry and Resource Objects</b></a>",
            "<ul>",
            "<li>Org/Users: <a href='/list/Org'>Org</a>, <a href='/list/UserRole'>UserRole</a>, <a href='/list/ActorIdentity'>ActorIdentity</a></li>",
            "<li>Computing: <a href='/list/Process'>Process</a>, <a href='/list/ProcessDefinition'>ProcessDefinition</a>, <a href='/list/Service'>Service</a>, <a href='/list/ServiceDefinition'>ServiceDefinition</a>, <a href='/list/CapabilityContainer'>CapabilityContainer</a></li>",
            "<li>Messaging: <a href='/list/ExchangeSpace'>ExchangeSpace</a>, <a href='/list/ExchangePoint'>ExchangePoint</a>, <a href='/list/ExchangeName'>ExchangeName</a>, <a href='/list/ExchangeBroker'>ExchangeBroker</a></li>",
            "<li>Governance: <a href='/list/Commitment'>Commitment</a>, <a href='/list/Negotiation'>Negotiation</a>, <a href='/list/Policy'>Policy</a></li>",
            _get_resmenu_extension(),
            "</ul></li>",
            "<li><a href='/events'><b>Browse Events</b></a></li>",
            "<li><a href='/viewobj'><b>View Objects</b></a></li>",
            "<li><a href='/viewstate'><b>View Process State</b></a></li>",
            "<li><a href='/dir'><b>Browse SciON Directory</b></a></li>",
            #"<li><a href='/mscweb'><b>Show system messages (MSCWeb)</b></a>",
            #"<ul>",
            #"<li><a href='/mscaction/stop'>Stop system message recording</a></li>",
            #"</ul></li>",
            "<li><a href='http://localhost:4000'><b>Application Web UI (if running)</b></a></li>",
            "<li><a href='http://" + CFG.get_safe("server.amqp.host") + ":15672/'><b>RabbitMQ Management UI (if running)</b></a></li>",
            "<li><a href='http://localhost:9001/'><b>Supervisord UI (if running)</b></a></li>",
            "</ul></p>",
            "<h2>System and Container Properties</h2>",
            "<p><table>",
            "<tr><th>Property</th><th>Value</th></tr>",
            "<tr><td>system.name (sysname)</td><td>%s</td></tr>" % get_sys_name(),
            "<tr><td>Message Broker</td><td>%s</td></tr>" % "%s:%s" % (CFG.server.amqp.host, CFG.server.amqp.port),
            "<tr><td>Database</td><td>%s</td></tr>" % "%s:%s" % (CFG.get_safe("server.%s.host" % default_ds_server), CFG.get_safe("server.%s.port" % default_ds_server)),
            "<tr><td>Container ID</td><td>%s</td></tr>" % Container.instance.id,
            "<tr><td>Read-Only</td><td>%s</td></tr>" % is_read_only(),
            "</table></p>",

            ]
        content = "\n".join(fragments)
        return build_page(content)

    except Exception as e:
        return build_error_page(traceback.format_exc())

# ----------------------------------------------------------------------------------------

@app.route('/restypes', methods=['GET','POST'])
def process_list_resource_types():
    try:
        type_list = set(getextends('Resource'))
        fragments = [
            build_standard_menu(),
            "<h1>List of Resource Types</h1>",
            "<p>",
        ]

        for restype in sorted(type_list):
            fragments.append("<a href='/list/%s'>%s</a>, " % (restype, restype))

        fragments.append("</p>")

        content = "\n".join(fragments)
        return build_page(content)

    except Exception as e:
        return build_error_page(traceback.format_exc())

# ----------------------------------------------------------------------------------------

@app.route('/alt/<namespace>/<alt_id>', methods=['GET'])
def process_alt_ids(namespace, alt_id):
    try:
        res_list, _ = Container.instance.resource_registry.find_resources_ext(alt_id_ns=namespace.encode('ascii'),
                                                                              alt_id=alt_id.encode('ascii'),
                                                                              access_args=get_rr_access_args())
        fragments = [
            build_standard_menu(),
            "<h1>List of Matching Resources: %s</h1>" % alt_id,
            "<p>",
            "<table>",
        ]
        fragments.extend([
            "<thead>",
            "<tr>",
            "<th>ID</th>",
            "<th>Name</th>",
            "<th>Description</th>",
            "<th>Resource Type</th>",
            "<th>alt_ids</th>",
            "</tr>",
            "</thead>"])
        fragments.append("<tbody>")

        for res in res_list:
            fragments.append("<tr>")
            fragments.extend(build_table_alt_row(res))
            fragments.append("</tr>")
        fragments.append("</tbody>")

        fragments.append("</table></p>")
        fragments.append("<p>Number of resources: %s</p>" % len(res_list))

        content = "\n".join(fragments)
        return build_page(content)

    except NotFound:
        return flask.redirect("/")
    except Exception:
        return build_error_page(traceback.format_exc())
        
# ----------------------------------------------------------------------------------------

@app.route('/list/<resource_type>', methods=['GET','POST'])
def process_list_resources(resource_type):
    try:
        restype = str(resource_type)
        with_details = get_arg("details", "off") == "on"

        res_list,_ = Container.instance.resource_registry.find_resources(restype=restype,
                                                                         access_args=get_rr_access_args())

        fragments = [
            build_standard_menu(),
            "<h1>List of '%s' Resources</h1>" % restype,
            build_command("Hide details" if with_details else "Show details", "/list/%s?details=%s" % (
                restype, "off" if with_details else "on")),
            build_command("New %s" % restype, "/new/%s" % restype),
            build_res_extends(restype),
            "<p>",
            "<table>",
            "<tr>"
        ]

        fragments.extend(build_table_header(restype))
        fragments.append("</tr>")

        for res in res_list:
            fragments.append("<tr>")
            fragments.extend(build_table_row(res, details=with_details))
            fragments.append("</tr>")

        fragments.append("</table></p>")
        fragments.append("<p>Number of resources: %s</p>" % len(res_list))

        content = "\n".join(fragments)
        return build_page(content)

    #except NotFound:
    #    return flask.redirect("/")
    except Exception as e:
        return build_error_page(traceback.format_exc())

def build_res_extends(restype):
    fragments = [
        "<p><i>Extends:</i> ",
    ]
    extendslist = [parent.__name__ for parent in _get_object_class(restype).__mro__ if parent.__name__ not in ['IonObjectBase','object']]
    for extend in extendslist:
        if extend != restype:
            fragments.append(build_link(extend, "/list/%s" % extend))
            fragments.append(", ")

    fragments.append("<br><i>Extended by:</i> ")
    for extends in sorted(getextends(restype)):
        if extends != restype:
            fragments.append(build_link(extends, "/list/%s" % extends))
            fragments.append(", ")

    fragments.append("</p>")

    return "".join(fragments)

def build_table_header(objtype):
    schema = _get_object_class(objtype)._schema
    fragments = []
    fragments.append("<th>ID</th>")
    for field in standard_resattrs:
        if field in schema:
            fragments.append("<th>%s</th>" % (field))
    for field in sorted(schema.keys()):
        if field not in standard_resattrs:
            fragments.append("<th>%s</th>" % (field))
    return fragments

def build_table_alt_row(obj):
    fragments = []
    fragments.extend([
        "<td><a href='/view/%s'>%s</a></td>" % (obj._id,obj._id),
        "<td>%s</td>" % obj.name,
        "<td>%s</td>" % obj.description,
        "<td><a href='/list/%s'>%s</a></td>" % (obj._get_type(),obj._get_type()),
        "<td>%s</td>" % obj.alt_ids])
    return fragments

def build_table_row(obj, details=True):
    schema = obj._schema
    fragments = []
    fragments.append("<td><a href='/view/%s'>%s</a></td>" % (obj._id,obj._id))
    for field in standard_resattrs:
        if field in schema:
            value = get_formatted_value(getattr(obj, field), fieldname=field, fieldtype=schema[field]["type"], details=True)
            fragments.append("<td>%s</td>" % (value))
    for field in sorted(schema.keys()):
        if field not in standard_resattrs:
            value = get_formatted_value(getattr(obj, field), fieldname=field, fieldtype=schema[field]["type"], brief=True, details=details)
            fragments.append("<td>%s</td>" % (value))
    return fragments

# ----------------------------------------------------------------------------------------

@app.route('/view/<resource_id>', methods=['GET','POST'])
def process_view_resource(resource_id):
    try:
        resid = str(resource_id)
        res = Container.instance.resource_registry.read(resid)
        restype = res._get_type()

        fragments = [
            build_standard_menu(),
            "<h1>View %s '%s'</h1>" % (build_type_link(restype), res.name),
            build_commands(resid, restype),
            "<h2>Fields</h2>",
            "<p>",
            "<table>",
            "<tr><th>Field</th><th>Type</th><th>Value</th></tr>"
            ]

        fragments.append("<tr><td>%s</td><td>%s</td><td>%s</td>" % ("type", "str", restype))
        fragments.append("<tr><td>%s</td><td>%s</td><td>%s</td>" % ("_id", "str", res._id))
        fragments.append("<tr><td>%s</td><td>%s</td><td>%s</td>" % ("_rev", "str", res._rev))
        fragments.extend(build_nested_obj(res, ""))
        fragments.append("</p></table>")
        fragments.extend(build_associations(res._id))
        fragments.append("<h2>Recent Events</h2>")

        events_list = Container.instance.event_repository.find_events(origin=resid,
                        descending=True, limit=50)

        fragments.extend(build_events_table(events_list))
        content = "\n".join(fragments)
        return build_page(content)

    except NotFound:
        return flask.redirect("/")
    except Exception as e:
        return build_error_page(traceback.format_exc())

def build_nested_obj(obj, prefix, edit=False):
    fragments = []
    schema = obj._schema
    for field in standard_resattrs:
        if field in schema:
            value = get_formatted_value(getattr(obj, field), fieldname=field, fieldtype=schema[field]["type"])
            if edit and field not in EDIT_IGNORE_FIELDS:
                fragments.append("<tr><td>%s%s</td><td>%s</td><td><input type='text' name='%s%s' value='%s' size='60'/></td>" % (prefix, field, schema[field]["type"], prefix, field, getattr(obj, field)))
            else:
                fragments.append("<tr><td>%s%s</td><td>%s</td><td>%s</td>" % (prefix, field, schema[field]["type"], value))
    for field in sorted(schema.keys()):
        if field not in standard_resattrs:
            value = getattr(obj, field)
            if schema[field]["type"] in model_classes or isinstance(value, IonObjectBase):
                value_type = value._get_type() if value else "None"
                # Nested object case
                fragments.append("<tr><td>%s%s</td><td>%s</td><td>%s</td>" % (prefix, field, schema[field]["type"], "[%s]" % value_type))
                if value:
                    fragments.extend(build_nested_obj(value, "%s%s." % (prefix,field), edit=edit))
            else:
                value = get_formatted_value(value, fieldname=field, fieldtype=schema[field]["type"])
                if edit and field not in EDIT_IGNORE_FIELDS and schema[field]["type"] not in EDIT_IGNORE_TYPES:
                    fragments.append("<tr><td>%s%s</td><td>%s</td><td><input type='text' name='%s%s' value='%s' size='60'/></td>" % (prefix, field, schema[field]["type"], prefix, field, getattr(obj, field)))
                else:
                    fragments.append("<tr><td>%s%s</td><td>%s</td><td>%s</td>" % (prefix, field, schema[field]["type"], value))
    return fragments

def build_associations(resid):
    fragments = list()

    fragments.append("<h2>Associations</h2>")
    fragments.append("<div id='chart'></div>")
    if CFG.get_safe(CFG_PREFIX + '.association_graph', True):
        #----------- Build the visual using javascript --------------#
        fragments.append("<script type='text/javascript' src='http://mbostock.github.com/d3/d3.v2.js'></script>   ")
        fragments.append("<script type='text/javascript' src='/static/tree-interactive.js'></script>")
        fragments.append("<script type='text/javascript'>build(\"%s\");</script>" % resid)
    #------------------------------------------------------------#
    fragments.append("<h3>FROM</h3>")
    fragments.append("<p><table>")
    fragments.append("<tr><th>Subject Type</th><th>Subject Name</th><th>Subject ID</th><th>Predicate</th><th>Command</th></tr>")
    obj_list, assoc_list = Container.instance.resource_registry.find_subjects(object=resid, id_only=False,
                                                                              access_args=get_rr_access_args())
    iter_list = sorted(zip(obj_list, assoc_list), key=lambda x: [x[1].p, x[0].type_, x[0].name])
    for obj, assoc in iter_list:
        fragments.append("<tr>")
        fragments.append("<td>%s</td><td>%s&nbsp;</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            build_type_link(obj.type_), obj.name, build_link(assoc.s, "/view/%s" % assoc.s),
            build_link(assoc.p, "/assoc?predicate=%s" % assoc.p),
            build_link("Delete", "/cmd/deleteassoc?rid=%s" % assoc._id, "return confirm('Are you sure to delete association?');")))

    fragments.append("</table></p>")
    fragments.append("<h3>TO</h3>")
    obj_list, assoc_list = Container.instance.resource_registry.find_objects(subject=resid, id_only=False,
                                                                             access_args=get_rr_access_args())

    fragments.append("<p><table>")
    fragments.append("<tr><th>Object Type</th><th>Object Name</th><th>Object ID</th><th>Predicate</th><th>Command</th></tr>")

    iter_list = sorted(zip(obj_list, assoc_list), key=lambda x: [x[1].p, x[0].type_, x[0].name])
    for obj, assoc in iter_list:
        fragments.append("<tr>")
        fragments.append("<td>%s</td><td>%s&nbsp;</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            build_type_link(obj.type_), obj.name, build_link(assoc.o, "/view/%s" % assoc.o),
            build_link(assoc.p, "/assoc?predicate=%s" % assoc.p),
            build_link("Delete", "/cmd/deleteassoc?rid=%s" % assoc._id, "return confirm('Are you sure to delete association?');")))

    fragments.append("</table></p>")
    return fragments

def build_commands(resource_id, restype):
    if is_read_only():
        return ""

    fragments = ["<h2>Commands</h2>"]

    fragments.append(build_command("Edit", "/edit/%s" % resource_id))

    fragments.append(build_command("Delete", "/cmd/delete?rid=%s" % resource_id, confirm="Are you sure to delete resource?"))

    options = [(p, p) for p in sorted(PRED)]
    args = [('select', 'pred', options), ('input', 'rid2', 45)]
    fragments.append(build_command("Associate from subject", "/cmd/createassoc?rid=%s&dir=from" % resource_id, args))
    fragments.append(build_command("Associate to object", "/cmd/createassoc?rid=%s&dir=to" % resource_id, args))

    from pyon.ion.resource import LCE, LCS, AS
    event_list = LCE.keys()
    options = zip(event_list, event_list)
    args = [('select', 'lcevent', options)]
    fragments.append(build_command("Execute Lifecycle Event", "/cmd/execute_lcs?rid=%s" % resource_id, args))

    state_list = LCS.keys() + AS.keys()
    options = zip(state_list, state_list)
    args = [('select', 'lcstate', options)]
    fragments.append(build_command("Change Lifecycle State", "/cmd/set_lcs?rid=%s" % resource_id, args))


    fragments.append("</table>")
    return "".join(fragments)

def build_command(text, link, args=None, confirm=None):
    fragments = []
    if args:
        arg_params = "'%s'" % link
        for arg in args:
            arg_type, arg_name, arg_more = arg
            arg_params += ",'%s','%s'" % (arg_name, arg_name)
        func_name = "linkto"
        if len(args) > 1:
            func_name += str(len(args))
        fragments.append("<div><a href='#' onclick=\"return %s(%s);\">%s</a> " % (func_name, arg_params, text))
        for arg in args:
            arg_type, arg_name, arg_more = arg
            if arg_type == "select":
                fragments.append("<select id='%s'>" % arg_name)
                for oname, oval in arg_more:
                    fragments.append("<option value='%s'>%s</option>" % (oval, oname))
                fragments.append("</select>")
            elif arg_type == "input":
                fragments.append("<input id='%s' type='text' size='%s'>" % (arg_name, arg_more or 30))
                fragments.append("</input>")
        fragments.append("</div>")
    else:
        if confirm:
            confirm = "return confirm('%s');" % confirm
        fragments.append("<div>%s</div>" % build_link(text, link, confirm))
    return "".join(fragments)

# ----------------------------------------------------------------------------------------

@app.route('/cmd/<cmd>', methods=['GET','POST'])
def process_command(cmd):
    try:
        cmd = str(cmd)
        resource_id = get_arg('rid')

        if is_read_only():
            raise Unauthorized("Cannot %s %s in read-only mode!" % (cmd, resource_id))

        res_obj = None
        if resource_id != "NEW" and cmd not in {'deleteassoc'}:
            res_obj = Container.instance.resource_registry.read(resource_id)

        func_name = "_process_cmd_%s" % cmd
        cmd_func = globals().get(func_name, None)
        if not cmd_func:
            raise Exception("Command %s unknown" % (cmd))

        result = cmd_func(resource_id, res_obj)

        fragments = [
            build_standard_menu(),
            "<h1>Command %s result</h1>" % cmd,
            "<p><pre>%s</pre></p>" % result,
            "<p>%s</p>" % build_link("Back to Resource Page", "/view/%s" % resource_id),
        ]

        content = "\n".join(fragments)
        return build_page(content)

    except Exception as e:
        return build_error_page(traceback.format_exc())

def _process_cmd_update(resource_id, res_obj=None):
    if resource_id == "NEW":
        restype = get_arg("restype")
        res_obj = IonObject(restype)

    schema = res_obj._schema
    set_fields = []

    for field,value in request.values.iteritems():
        value = str(value)
        nested_fields = field.split('.')
        local_field = nested_fields[0]
        if field in EDIT_IGNORE_FIELDS or local_field not in schema:
            continue
        if len(nested_fields) > 1:
            obj = res_obj
            skip_field = False
            for sub_field in nested_fields:
                local_obj = getattr(obj, sub_field, None)
                if skip_field or local_obj is None:
                    skip_field = True
                    continue
                elif isinstance(local_obj, IonObjectBase):
                    obj = local_obj
                else:
                    value = get_typed_value(value, obj._schema[sub_field])
                    setattr(obj, sub_field, value)
                    set_fields.append(field)
                    skip_field = True

        elif schema[field]['type'] in EDIT_IGNORE_TYPES:
            pass
        else:
            value = get_typed_value(value, res_obj._schema[field])
            setattr(res_obj, field, value)
            set_fields.append(field)

    #res_obj._validate()

    if resource_id == "NEW":
        Container.instance.resource_registry.create(res_obj)
    else:
        Container.instance.resource_registry.update(res_obj)

    return "OK. Set fields:\n%s" % pprint.pformat(sorted(set_fields))

def _process_cmd_createassoc(resource_id, res_obj=None):
    pred = get_arg("pred", None)
    direction = get_arg("dir", None)
    if not all([pred, direction]):
        raise BadRequest("Must provide all arguments")
    rid2 = get_arg("rid2", None)
    if not rid2:
        raise BadRequest("Must provide target resource id")
    rid2_obj = Container.instance.resource_registry.read(rid2)
    if direction == "from":
        Container.instance.resource_registry.create_association(rid2, pred, resource_id)
    elif direction == "to":
        Container.instance.resource_registry.create_association(resource_id, pred, rid2)
    return "OK"

def _process_cmd_delete(resource_id, res_obj=None):
    Container.instance.resource_registry.delete(resource_id)
    return "OK"

def _process_cmd_deleteassoc(resource_id, res_obj=None):
    Container.instance.resource_registry.delete_association(resource_id)
    return "OK"

def _process_cmd_set_lcs(resource_id, res_obj=None):
    lcstate = get_arg('lcstate')
    Container.instance.resource_registry.set_lifecycle_state(resource_id, lcstate)
    return "OK"

def _process_cmd_execute_lcs(resource_id, res_obj=None):
    lcevent = get_arg('lcevent')
    new_state = Container.instance.resource_registry.execute_lifecycle_transition(resource_id, lcevent)
    return "OK. New state: %s" % new_state


# ----------------------------------------------------------------------------------------

@app.route('/edit/<resource_id>', methods=['GET','POST'])
def process_edit_resource(resource_id):
    try:
        resid = str(resource_id)
        res = Container.instance.resource_registry.read(resid)
        restype = res._get_type()

        fragments = [
            build_standard_menu(),
            "<h1>Edit %s '%s'</h1>" % (build_type_link(restype), res.name),
            "<form name='edit' action='/cmd/update?rid=%s' method='post'>" % resid,
        ]
        fragments.extend(build_editable_resource(res, is_new=False))
        fragments.append("<p><input type='reset'/> <input type='submit' value='Save'/></p>")
        fragments.append("</form>")
        fragments.append("<p>%s</p>" % build_link("Back to Resource Page", "/view/%s" % resid)),

        content = "\n".join(fragments)
        return build_page(content)

    except NotFound:
        return flask.redirect("/")
    except Exception as e:
        return build_error_page(traceback.format_exc())

@app.route('/new/<restype>', methods=['GET','POST'])
def process_new_resource(restype):
    try:
        restype = str(restype)
        res = IonObject(restype)
        res._id = "NEW"
        for k,v in request.args.iteritems():
            if '.' in k:
                key = None
                obj = res
                attrs = k.split('.')
                while len(attrs):
                    key = attrs.pop(0)
                    if not len(attrs):
                        if hasattr(obj,key):
                            setattr(obj,key,v)
                            break
                    if hasattr(obj,key):
                        obj = getattr(obj,key)
                    else:
                        break

            elif hasattr(res,k):
                setattr(res,k,v)

        fragments = [
            build_standard_menu(),
            "<h1>Create New %s</h1>" % (build_type_link(restype)),
            "<form name='edit' action='/cmd/update?rid=NEW&restype=%s' method='post'>" % restype,
        ]
        fragments.extend(build_editable_resource(res, is_new=True))
        fragments.append("<p><input type='reset'/> <input type='submit' value='Create'/></p>")
        fragments.append("</form>")
        fragments.append("<p>%s</p>" % build_link("Back to List Page", "/list/%s" % restype)),

        content = "\n".join(fragments)
        return build_page(content)

    except NotFound:
        return flask.redirect("/")
    except Exception as e:
        return build_error_page(traceback.format_exc())

def build_editable_resource(res, is_new=False):
    restype = res._get_type()
    resid = res._id

    fragments = [
        "<p><table>",
        "<tr><th>Field</th><th>Type</th><th>Value</th></tr>"
    ]

    fragments.append("<tr><td>%s</td><td>%s</td><td>%s</td>" % ("type", "str", restype))
    fragments.extend(build_nested_obj(res, "", edit=True))
    fragments.append("</p></table>")

    return fragments

# ----------------------------------------------------------------------------------------

@app.route('/assoc', methods=['GET','POST'])
def process_assoc_list():
    try:
        predicate = get_arg('predicate')

        assoc_list = Container.instance.resource_registry.find_associations(predicate=predicate, id_only=False,
                                                                            access_args=get_rr_access_args())

        fragments = [
            build_standard_menu(),
            "<h1>List of Associations</h1>",
            "<p>Restrictions: predicate=%s</p>" % (predicate),
            "<p>",
            "<table>",
            "<tr><th>Subject</th><th>Subject type</th><th>Predicate</th><th>Object ID</th><th>Object type</th></tr>"
        ]

        for assoc in assoc_list:
            fragments.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                build_link(assoc.s, "/view/%s" % assoc.s), build_type_link(assoc.st), assoc.p, build_link(assoc.o, "/view/%s" % assoc.o), build_type_link(assoc.ot)))

        fragments.append("</table></p>")

        content = "\n".join(fragments)
        return build_page(content)

    except NotFound:
        return flask.redirect("/")
    except Exception as e:
        return build_error_page(traceback.format_exc())

# ----------------------------------------------------------------------------------------

@app.route('/dir', methods=['GET','POST'], defaults={'path':'~'})
@app.route('/dir/<path>', methods=['GET','POST'])
def process_dir_path(path):
    try:
        #path = convert_unicode(path)
        path = str(path)
        path = path.replace("~", "/")

        fragments = [
            build_standard_menu(),
            "<h1>Directory %s</h1>" % (build_dir_path(path)),
            "<h2>Attributes</h2>",
            "<p><table><tr><th>Name</th><th>Value</th></tr>"
        ]

        entry = Container.instance.directory.lookup(path)
        if entry:
            for attr in sorted(entry.keys()):
                attval = entry[attr]
                fragments.append("<tr><td>%s</td><td>%s</td></tr>" % (attr, attval))
        fragments.append("</table></p>")

        fragments.append("</p><h2>Child Entries</h2><p><table><tr><th>Key</th><th>Timestamp</th><th>Attributes</th></tr>")
        de_list = Container.instance.directory.find_child_entries(path)
        for de in de_list:
            if '/' in de.parent:
                org, parent = de.parent.split("/", 1)
                parent = "/"+parent
            else:
                parent = ""
            fragments.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                build_dir_link(parent,de.key), get_formatted_value(de.ts_updated, fieldname="ts_updated"), get_formatted_value(get_value_dict(de.attributes), fieldtype="dict")))

        fragments.append("</table></p>")

        content = "\n".join(fragments)
        return build_page(content)

    except NotFound:
        return flask.redirect("/")
    except Exception as e:
        return build_error_page(traceback.format_exc())

def build_dir_path(path):
    if path.startswith('/'):
        path = path[1:]
    levels = path.split("/")
    fragments = []
    parent = ""
    for level in levels:
        fragments.append(build_dir_link(parent,level))
        fragments.append("/")
        parent = "%s/%s" % (parent, level)
    return "".join(fragments)

def build_dir_link(parent, key):
    if parent == "/":
        path = "/%s" % (key)
    else:
        path = "%s/%s" % (parent, key)
    path = path.replace("/","~")
    return build_link(key, "/dir/%s" % path)

# ----------------------------------------------------------------------------------------

@app.route('/events', methods=['GET','POST'])
def process_events():
    try:
        event_type = request.args.get('event_type', None)
        origin = request.args.get('origin', None)
        limit = int(request.args.get('limit', 100))
        descending = request.args.get('descending', True)
        skip = int(request.args.get('skip', 0))

        events_list = Container.instance.event_repository.find_events(event_type=event_type, origin=origin,
                                     descending=descending, limit=limit, skip=skip)

        fragments = [
            build_standard_menu(),
            "<h1>List of Events</h1>",
            "Restrictions: event_type=%s, origin=%s, limit=%s, descending=%s, skip=%s" % (event_type, origin, limit, descending, skip),
        ]

        fragments.extend(build_events_table(events_list))

        if len(events_list) >= limit:
            fragments.append("<p>%s</p>" % build_link("Next page", "/events?skip=%s" % (skip + limit)))

        content = "\n".join(fragments)
        return build_page(content)

    except NotFound:
        return flask.redirect("/")
    except Exception as e:
        return build_error_page(traceback.format_exc())

def build_events_table(events_list):
    fragments = [
        "<p><table>",
        "<tr><th>Timestamp</th><th>Event type</th><th>Sub-type</th><th>Origin</th><th>Origin type</th><th>Other Attributes</th><th>Description</th></tr>"
    ]

    ignore_fields=["base_types", "origin", "description", "ts_created", "sub_type", "origin_type", "_rev", "_id"]
    for event_id, event_key, event in events_list:
        fragments.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            get_formatted_value(event.ts_created, fieldname="ts_created", time_millis=True),
            build_link(event._get_type(), "/events?event_type=%s" % event._get_type()),
            event.sub_type or "&nbsp;",
            build_link(event.origin, "/view/%s" % event.origin),
            event.origin_type or "&nbsp;",
            get_formatted_value(get_value_dict(event, ignore_fields=ignore_fields), fieldtype="dict"),
            event.description  or "&nbsp;"))

    fragments.append("</table></p>")

    return fragments

# ----------------------------------------------------------------------------------------

@app.route('/viewobj', methods=['GET','POST'])
def process_view_objects():
    try:
        obj_filter = get_arg('filter')
        obj_id = get_arg('object_id')
        args_filter = [('input', 'filter', 45)]
        args_view = [('input', 'object_id', 45)]
        fragments = [
            build_standard_menu(),
            "<h1>View Objects</h1>",
            "<h2>Filter</h2>",
            build_link("All Objects", "/viewobj?filter=*"),
            build_command("Object ID pattern", "/viewobj?dummy=1", args_filter),
            build_command("Object ID", "/viewobj?dummy=1", args_view),
        ]
        if obj_filter:
            fragments.append("<h2>Object List</h2>")
            fragments.append("<p>")

            obj_ids = Container.instance.object_store.obj_store.list_objects()
            fragments.append("<p><table>")
            fragments.append("<tr><th>Object ID</th></tr>")
            for oid in obj_ids:
                if obj_filter == "*" or obj_filter in oid:
                    fragments.append("<tr>")
                    fragments.append("<td>%s</td></tr>" % (build_link(oid, "/viewobj?object_id=%s" % oid)))

            fragments.append("</table></p>")
            fragments.append("</p>")

        if obj_id:
            fragments.append("<h2>Object Details</h2>")
            fragments.append("<p><pre>")
            obj = Container.instance.object_store.read_doc(obj_id)
            value = yaml.dump(obj, default_flow_style=False, Dumper=yaml.CDumper)
            fragments.append(value)
            fragments.append("</pre></p>")

        content = "\n".join(fragments)
        return build_page(content)

    except Exception as e:
        return build_error_page(traceback.format_exc())

# ----------------------------------------------------------------------------------------

@app.route('/viewstate', methods=['GET','POST'])
def process_view_state():
    try:
        state_id = get_arg('state_id')
        args_view = [('input', 'state_id', 45)]
        fragments = [
            build_standard_menu(),
            "<h1>View State</h1>",
            build_command("State ID", "/viewstate?dummy=1", args_view),
        ]
        if state_id:
            fragments.append("<h2>State Details</h2>")
            fragments.append("<p><pre>")
            obj_state, obj = Container.instance.state_repository.get_state(state_id)
            if obj:
                value = yaml.dump(obj_state, default_flow_style=False, Dumper=yaml.CDumper)
                fragments.append(value)
            fragments.append("</pre></p>")

        content = "\n".join(fragments)
        return build_page(content)

    except Exception as e:
        return build_error_page(traceback.format_exc())

# ----------------------------------------------------------------------------------------

@app.route('/map', methods=['GET'])
def process_map():
    '''
    Map!
    '''
    try:
        content = [
            "        <script type='text/javascript' src='http://ajax.googleapis.com/ajax/libs/jquery/1.7.1/jquery.min.js'> </script>",
            "        <script type='text/javascript' src='https://maps.googleapis.com/maps/api/js?sensor=false'></script>",
            "<div id='map_canvas'></div>",
            "<script type='text/javascript' src='/static/gmap.js'></script>",
        ]
        content = "\n".join(content)
        return build_page(content)
    except Exception as e:
        return build_error_page(traceback.format_exc())


# ----------------------------------------------------------------------------------------

@app.route('/tree/<resid>', methods=['GET'])
def process_tree(resid):
    '''
    Creates a tree-like JSON string to be parsed by visual clients such as the D3 Framework
    @param resid Resource id
    @return An HTTP Response containing the JSON string (Content-Type: application/json)
    '''
    from flask import make_response, Response
    from ion.services.utility.resource_tree import build
    try:
        resp = make_response(Response(),200)
        data = build(resid).to_j()
        resp.data = data
        resp.headers['Content-Type'] = 'application/json'
        resp.headers['Content-Length'] = len(data)
        return resp
    except Exception as e:
        return build_error_page(traceback.format_exc())

# ----------------------------------------------------------------------------------------

def is_read_only():
    return CFG.get_safe(CFG_PREFIX + '.read_only', False)

def get_rr_access_args(as_superuser=True):
    """Return RR access args for search result filtering. For now superuser level.
    TODO: Use logged in user permissions or override
    """
    return dict(current_actor_id="SUPERUSER", superuser_actor_ids=["SUPERUSER"])

def build_type_link(restype):
    return build_link(restype, "/list/%s" % restype)

def build_link(text, link, onclick=None):
    if onclick:
        return "<a href='%s' onclick=\"%s\">%s</a>" % (link, onclick, text)
    else:
        return "<a href='%s'>%s</a>" % (link, text)

def build_standard_menu():
    return "<p><a href='/'>[Home]</a></p>"

def build_error_page(msg):
    fragments = [
        build_standard_menu(),
        "<h1>Error</h1>",
        "<p><pre>%s</pre></p>" % msg,
    ]
    content = "\n".join(fragments)
    return build_page(content)

def build_simple_page(content):
    return build_page("<p><pre>" + content + "</pre></p>")

def build_page(content, title=""):
    fragments = [
        "<!doctype html>",
        "<html><head>",
        "<link type='text/css' rel='stylesheet' href='/static/default.css' />"
        "<link type='text/css' rel='stylesheet' href='/static/demo.css' />",
        "<script type='text/javascript'>",
        "function linkto(href, arg_name, arg_id) {",
        "var aval = document.getElementById(arg_id).value;",
        "href = href + '&' + arg_name + '=' + aval;",
        "window.location.href = href;",
        "return true;",
        "}",
        "function linkto2(href, arg_name, arg_id, arg_name2, arg_id2) {",
        "var aval = document.getElementById(arg_id).value;",
        "var aval2 = document.getElementById(arg_id2).value;",
        "href = href + '&' + arg_name + '=' + aval + '&' + arg_name2 + '=' + aval2;",
        "window.location.href = href;",
        "return true;",
        "}",
        "</script></head>"
        "<body>",
        content,
        "</body></html>"
    ]
    return "\n".join(fragments)

def get_arg(arg_name, default=None):
    aval = request.values.get(arg_name, None)
    return str(aval) if aval else default

def convert_unicode(data):
    """
    Used to recursively convert unicode in JSON structures into proper data structures
    """
    if isinstance(data, unicode):
        return str(data)
    elif isinstance(data, collections.Mapping):
        return dict(map(convert_unicode, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(convert_unicode, data))
    else:
        return data

obj_classes = {}

def _get_object_class(objtype):
    if objtype in obj_classes:
        return obj_classes[objtype]
    obj_class = named_any("interface.objects.%s" % objtype)
    obj_classes[objtype] = obj_class
    return obj_class

def get_typed_value(value, schema_entry=None, targettype=None):
    targettype = targettype or schema_entry["type"]
    if targettype is 'str':
        return str(value)
    elif targettype is 'bool':
        lvalue = value.lower()
        if lvalue == 'true':
            return True
        elif lvalue == 'false' or lvalue == '':
            return False
        else:
            raise BadRequest("Value %s is no bool" % value)
    elif targettype is 'simplelist':
        if value.startswith('[') and value.endswith(']'):
            value = value[1:len(value)-1].strip()
        return list(value.split(','))
    elif schema_entry and 'enum_type' in schema_entry:
        enum_clzz = getattr(objects, schema_entry['enum_type'])
        if type(value) is str and value in enum_clzz._value_map:
            return enum_clzz._value_map[value]
        else:
            return int(value)
    else:
        return ast.literal_eval(value)


def get_value_dict(obj, ignore_fields=None):
    ignore_fields = ignore_fields or []
    if isinstance(obj, IonObjectBase):
        obj_dict = obj.__dict__
    else:
        obj_dict = obj
    val_dict = {}
    for k,val in obj_dict.iteritems():
        if k in ignore_fields:
            continue
        if isinstance(val, IonObjectBase):
            vdict = get_value_dict(val)
            val_dict[k] = vdict
        else:
            val_dict[k] = val
    return val_dict

def get_formatted_value(value, fieldname=None, fieldtype=None, fieldschema=None, brief=False, time_millis=False,
                        is_root=True, details=True):
    if not fieldtype and fieldschema:
        fieldtype = fieldschema['type']
    if isinstance(value, IonObjectBase):
        if brief:
            value = "[%s]" % value.type_
    elif fieldtype in ("list", "dict"):
        if details:
            value = yaml.dump(value, default_flow_style=False, Dumper=yaml.CDumper)
            value = value.replace("\n", "<br>")
            if value.endswith("<br>"):
                value = value[:-4]
            if is_root:
                value = "<span class='preform'>%s</span>" % value
        else:
            value = "..."
    elif fieldschema and 'enum_type' in fieldschema:
        enum_clzz = getattr(objects, fieldschema['enum_type'])
        return enum_clzz._str_map[int(value)]
    elif fieldname:
        if fieldname in date_fieldnames:
            try:
                value = get_datetime(value, time_millis)
            except Exception:
                pass
    if value == "":
        return "&nbsp;"
    return value


def get_datetime(ts, time_millis=False):
    tsf = float(ts) / 1000
    dt = datetime.datetime.fromtimestamp(time.mktime(time.localtime(tsf)))
    dts = str(dt)
    if time_millis:
        dts += "." + ts[-3:]
    return dts
