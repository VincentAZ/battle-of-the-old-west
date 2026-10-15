"""Read only the clipboard after this test's own Copy click, using installed X11.

No clipboard text is written to logs or returned on mismatch. This is a Linux
X11/XWayland probe, not Windows clipboard validation. Importing starts no GUI.
"""
import ctypes as C
import ctypes.util
import time


class SelectionEvent(C.Structure):
    _fields_ = [('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),
        ('display',C.c_void_p),('requestor',C.c_ulong),('selection',C.c_ulong),
        ('target',C.c_ulong),('property',C.c_ulong),('time',C.c_ulong)]


class Event(C.Union):
    _fields_ = [('type',C.c_int),('selection',SelectionEvent),('pad',C.c_long*24)]


def clipboard_matches(expected, timeout=4.):
    assert isinstance(expected,str) and len(expected) <= 253 and expected.isascii()
    library = ctypes.util.find_library('X11')
    if not library:
        raise RuntimeError('Installed libX11 clipboard reader is unavailable')
    x = C.CDLL(library)
    signatures = {
        'XOpenDisplay':([C.c_char_p],C.c_void_p),
        'XDefaultRootWindow':([C.c_void_p],C.c_ulong),
        'XCreateSimpleWindow':([C.c_void_p,C.c_ulong,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_uint,C.c_ulong,C.c_ulong],C.c_ulong),
        'XInternAtom':([C.c_void_p,C.c_char_p,C.c_int],C.c_ulong),
        'XGetSelectionOwner':([C.c_void_p,C.c_ulong],C.c_ulong),
        'XConvertSelection':([C.c_void_p,C.c_ulong,C.c_ulong,C.c_ulong,C.c_ulong,C.c_ulong],C.c_int),
        'XFlush':([C.c_void_p],C.c_int),'XPending':([C.c_void_p],C.c_int),
        'XNextEvent':([C.c_void_p,C.POINTER(Event)],C.c_int),
        'XGetWindowProperty':([C.c_void_p,C.c_ulong,C.c_ulong,C.c_long,C.c_long,C.c_int,C.c_ulong,
            C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),
            C.POINTER(C.POINTER(C.c_ubyte))],C.c_int),
        'XFree':([C.c_void_p],C.c_int),'XDestroyWindow':([C.c_void_p,C.c_ulong],C.c_int),
        'XCloseDisplay':([C.c_void_p],C.c_int)}
    for name,(args,result) in signatures.items():
        function=getattr(x,name); function.argtypes=args; function.restype=result
    display=x.XOpenDisplay(None)
    if not display:
        raise RuntimeError('Cannot open current X11/XWayland display for clipboard verification')
    window=0
    try:
        window=x.XCreateSimpleWindow(display,x.XDefaultRootWindow(display),0,0,1,1,0,0,0)
        if not window:
            raise RuntimeError('Cannot create clipboard selection request window')
        selection=x.XInternAtom(display,b'CLIPBOARD',0)
        target=x.XInternAtom(display,b'UTF8_STRING',0)
        prop=x.XInternAtom(display,b'OLDWEST_TEST_COPIED_ENDPOINT',0)
        if not x.XGetSelectionOwner(display,selection):
            raise RuntimeError('Clipboard has no owner after the tested Copy click')
        x.XConvertSelection(display,selection,target,prop,window,0);x.XFlush(display)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if not x.XPending(display):
                time.sleep(.02);continue
            event=Event();x.XNextEvent(display,C.byref(event))
            e=event.selection
            if event.type != 31 or e.requestor != window or e.selection != selection or e.target != target:
                continue
            if not e.property:
                raise RuntimeError('Clipboard owner declined UTF8_STRING conversion after Copy')
            actual_type=C.c_ulong();format_=C.c_int();items=C.c_ulong();remaining=C.c_ulong()
            raw=C.POINTER(C.c_ubyte)()
            status=x.XGetWindowProperty(display,window,prop,0,64,1,0,C.byref(actual_type),C.byref(format_),
                C.byref(items),C.byref(remaining),C.byref(raw))
            try:
                valid=status==0 and actual_type.value==target and format_.value==8 and remaining.value==0 and items.value<=253
                matches=valid and C.string_at(raw,items.value)==expected.encode('ascii')
                return {'matches_expected_endpoint':bool(matches),'backend':'libX11 UTF8_STRING selection',
                    'actual_byte_count':items.value if valid else None,'unexpected_clipboard_text_recorded':False}
            finally:
                if raw:x.XFree(raw)
        raise RuntimeError('Clipboard selection did not respond within the bounded timeout')
    finally:
        if window:x.XDestroyWindow(display,window)
        x.XCloseDisplay(display)
