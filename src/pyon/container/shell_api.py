#!/usr/bin/env python

"""Provides the interactive API for the pyon container."""

__author__ = 'Michael Meisinger'

container = None


def get_console_dimensions():
    """Returns (rowns, columns) of current terminal"""
    import os
    rows, columns = os.popen('stty size', 'r').read().split()
    return int(rows), int(columns)

def get_max_width(table, index):
    """Get the maximum width of the given column index"""
    return max([len(str(row[index])) for row in table])

def pprint_table(table, pad=1, indent=0, trunc=None):
    """Prints out a table of data, padded for alignment
    @param out: Output stream (file-like object)
    @param table: The table to print. A list of lists.
    @param trunc: List of integers to truncate table to
    Each row must have the same number of columns.
    From:http://ginstrom.com/scribbles/2007/09/04/pretty-printing-a-table-in-python/
    """
    if len(table) == 0:
        return ""
    strl = []

    col_paddings = []
    for i in xrange(len(table[0])):
        if trunc and trunc[i] != 0:
            col_paddings.append(abs(trunc[i]))
        else:
            col_paddings.append(get_max_width(table, i))

    for row in table:
        strl.append(' ' * indent)
        for i in xrange(len(row)):
            col = str(row[i])
            if trunc and trunc[i] > 2 and len(col) > trunc[i]:
                col = col[0:trunc[i] - 2] + ".."
            elif trunc and trunc[i]<-2 and len(col) > abs(trunc[i]):
                col = ".." + col[trunc[i] + 2:]
            col = col.ljust(col_paddings[i] + pad)
            strl.append(col)
        strl.append('\n')

    return "".join(strl)

def pprint_list(l, c, pad=1, indent=0):
    """Pretty prints a list as table and returns string.
    @param l list to print
    @param c number of columns or -1 to optimize for console width
    @param pad whitespace padding between columns (1)
    @param indent whitespace indent
    """
    if c == -1:
        try:
            rows, columns = get_console_dimensions()

            table_n = None
            for c in xrange(1, min(columns / (pad + 1), len(l))):
                table = table_n
                table_n = [l[c * i:c * i + c] for i in range(1 + len(l) / c)]
                table_n[-1].extend([''] * (c - len(table_n[-1])))
                sumwid = indent
                for i in xrange(c):
                    sumwid += get_max_width(table_n, i)
                sumwid += pad * c
                if sumwid > columns:
                    if not table:
                        table = table_n
                    break
        except Exception:
            return pprint_list(l, 1, pad, indent)
    else:
        table = [l[c * i:c * i + c] for i in range(1 + len(l) / c)]
        table_n[-1].extend([''] * (c - len(table_n[-1])))

    return pprint_table(table, pad, indent)

# -------------------------------------------------

def ps(ret=False):
    print "List of ION processes"
    print "---------------------"
    print "\n".join(("%s: %s" % (name, p) for (name, p) in container.proc_manager.procs.iteritems()))
    if ret:
        return container.proc_manager.procs

def procs(ret=False):
    print "\nList of pyon processes"
    print "----------------------"
    print "\n".join((str(p) for p in container.proc_manager.proc_sup.children))
    if ret:
        return container.proc_manager.proc_sup.children

def procmap():
    from pyon.ion.resource import RT, PRED
    from interface.objects import ProcessStateEnum
    # Get Process resources
    proc_objs, _ = container.resource_registry.find_resources(RT.Process, id_only=False)
    # Get CapabilityContainer resources
    cc_objs, _ = container.resource_registry.find_resources(RT.CapabilityContainer, id_only=False)
    # Get associations
    assocs = container.resource_registry.find_associations(predicate=PRED.hasProcess, id_only=False)

    proc_by_id = {o._id: o for o in proc_objs}
    cc_by_id = {o._id: o for o in cc_objs}
    procs_by_cc = {}
    for assoc in assocs:
        if assoc.st == RT.CapabilityContainer and assoc.ot == RT.Process:
            if assoc.s in cc_by_id and assoc.o in proc_by_id:
                procs_by_cc.setdefault(assoc.s, []).append(assoc.o)

    print "Map of system processes"
    print "-----------------------"

    for cc in sorted(cc_objs, key=lambda o: o.name):
        print "CC {} @ {} ({})".format(cc.name, cc.container_info["host"], cc.container_info["hostname"])
        for pid in sorted(procs_by_cc.get(cc._id, []), key=lambda o: proc_by_id[o].name):
            proc = proc_by_id[pid]
            if proc.process_state == ProcessStateEnum.RUNNING:
                print "   {} ({}) - {} '{}'".format(proc.name, proc.label, proc.process_type, proc.service_name)

def ms():
    print "List of messaging endpoints"
    print "---------------------------"
    print "(TBD)"

def apps():
    print "List of active pyon apps"
    print "------------------------"
    print "\n".join(("%s: %s" % (appdef.name, appdef) for appdef in container.app_manager.apps))

def svc_defs(svcs=None, op=None):
    """Returns service definitions for service name(s)
    @param svcs name or list of names of service
    """
    from pyon.core.bootstrap import get_service_registry

    if not getattr(svcs, '__iter__', False) and op is not None:
        svcdef = get_service_registry().services[svcs]
        print "Service definition for: %s (version %s) operation %s" % (svcs, svcdef.version or 'ND', op)
        print "".join([str(o) for o in svcdef.operations if o.name == op])
        return svcdef

    elif svcs is not None:
        if not getattr(svcs, '__iter__', False):
            svcs = (svcs,)
        for svcname in svcs:
            svcdef = get_service_registry().services[svcname]
            svcops = "\n     ".join(sorted([o.name for o in svcdef.operations]))
            print "Service definition for: %s (version %s)" % (svcname, svcdef.version or 'ND')
            print "ops: %s" % (svcops)
            return svcdef

    else:
        print "List of defined services"
        print "------------------------"

        for svcname in sorted(get_service_registry().services.keys()):
            svcdef = get_service_registry().services[svcname]
            print "%s %s" % (svcname, svcdef.version)

        print "\nType svc_defs('name') or svc_defs(['name1','name2']) for definition"
        return None

def obj_defs(ob=None):
    """Returns object definitions for object name(s)
    @param ob name or list of names of object
    """
    from pyon.core.bootstrap import get_obj_registry

    if ob is not None:
        print "Object definition for: %s\n" % ob

        if not getattr(ob, '__iter__', False):
            ob = (ob,)
        for o in ob:
            print get_obj_registry().instances_by_name[o]

    else:
        print "List of defined objects"
        print "-----------------------"
        onames = sorted(get_obj_registry().instances_by_name.keys())
        print pprint_list(onames, -1, 1, 2)
        print "\nType obj_defs('name') or obj_defs(['name1','name2']) for definition"


def type_defs(ob=None):
    """Returns object type definitions for object name(s)
    @param ob name or list of names of object
    """
    from pyon.core.bootstrap import get_obj_registry

    if ob is not None:
        print "Type definition for: %s\n" % ob

        if not getattr(ob, '__iter__', False):
            ob = (ob,)
        for o in ob:
            print get_obj_registry().type_by_name[o]

    else:
        print "List of defined objects"
        print "-----------------------"
        tnames = sorted(get_obj_registry().type_by_name.keys())
        print pprint_list(tnames, -1, 1, 2)
        print "\nType type_defs('name') or type_defs(['name1','name2']) for definition"


def lsdir(qname='/', truncate=True):
    """Prints all directory entries below the given node.
    @param qname the directory node (must start with '/')
    """
    ds = container.directory
    delist = ds.find_child_entries(qname)
    detable = [(str(de._id), str(de.attributes)) for de in delist]

    if len(detable) == 0:
        print
        return
    if truncate:
        rows, columns = get_console_dimensions()
        col1wid = get_max_width(detable, 0)
        col1max = min(50 if columns > 50 else 0, col1wid)
        print pprint_table(detable, trunc=[-col1max, columns - col1max - 2 if columns > col1max + 3 else 0])
    else:
        print "\n".join(["%s: %s" % tup for tup in detable])


def spawn(proc, procname=None):
    procmod, proccls = proc.rsplit('.', 1)
    procname = procname or proccls
    container.spawn_process(procname, procmod, proccls)

def start_mx():
    from pyon.public import CFG
    port = CFG.get_safe('process.admin_ui.web_server.port', 8080)
    container.spawn_process("admin_ui", "ion.process.ui.admin_ui", "AdminUI")
    print "pycc: SciON Admin UI started ... listening on http://localhost:%s" % port


def ionhelp():
    print "ScionCC interactive shell"
    print
    print "Available functions: %s" % ", ".join(sorted([func.__name__ for func in public_api]))
    print "Available variables: %s" % ", ".join(sorted(public_vars.keys()))

# This defines the public API of functions
public_api = [ionhelp, ps, procs, procmap, ms, apps, svc_defs, obj_defs, type_defs, lsdir, spawn, start_mx]
public_vars = None


def get_proc():
    from pyon.util.containers import DotDict
    procs = DotDict(container.proc_manager.procs)
    pn = DotDict(container.proc_manager.procs_by_name)
    return procs, pn


def define_vars():
    from pyon.core.bootstrap import CFG as cfg
    if public_vars: return public_vars
    cc = container
    proc, pn = get_proc()
    if cc.instance.has_capability(cc.instance.CCAP.RESOURCE_REGISTRY):
        rr = cc.instance.resource_registry
    if cc.instance.has_capability(cc.instance.CCAP.GOVERNANCE_CONTROLLER):
        govc = cc.instance.governance_controller
    CFG = cfg
    return locals()


def get_shell_api(cc):
    """Returns an API to introspect and manipulate the container
    @retval dict that can be added to locals() namespace
    """
    global container
    global public_vars
    container = cc

    ns_dict = dict()
    for func in public_api:
        ns_dict[func.__name__] = func
    public_vars = define_vars()
    ns_dict.update(public_vars)

    return ns_dict
