__major__ = 0
__minor__ = 2
__extra__ = 11
__stage__ = "b"
__pr__ = 12

__version__ = "%d.%d.%d" % (
        __major__,
        __minor__,
        __extra__)

__release__ = "%s%s%d" % (
        __version__,
        __stage__,
        __pr__)
