

import logging
import logging.handlers
import sys
import threading

_configured = False
logger = logging.getLogger("solrich")


class _Tee:
    

    def __init__(self, orig, level):
        self._orig = orig
        self._level = level
        self._buf = ""

    def write(self, s):
        try:
            if self._orig is not None:
                self._orig.write(s)
        except Exception:
            pass
        try:
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line.strip():
                    logger.log(self._level, line)
        except Exception:
            pass

    def flush(self):
        try:
            if self._orig is not None:
                self._orig.flush()
        except Exception:
            pass

    def isatty(self):
        try:
            return bool(self._orig) and self._orig.isatty()
        except Exception:
            return False


def setup(log_dir):
    
    global _configured
    if _configured:
        return
    _configured = True
    try:
        from pathlib import Path
        path = Path(log_dir) / "solrich.log"
        handler = logging.handlers.RotatingFileHandler(
            str(path), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.propagate = False

        sys.stdout = _Tee(getattr(sys, "stdout", None), logging.INFO)
        sys.stderr = _Tee(getattr(sys, "stderr", None), logging.ERROR)

        def _excepthook(exc_type, exc, tb):
            logger.error("Uncaught exception", exc_info=(exc_type, exc, tb))
        sys.excepthook = _excepthook

        if hasattr(threading, "excepthook"):
            def _thread_excepthook(args):
                logger.error(
                    "Uncaught exception in thread %s",
                    getattr(args, "thread", None),
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
            threading.excepthook = _thread_excepthook

        logger.info("=== SolRich logging started ===")
    except Exception as e:
        try:
            print(f"[applog] setup failed: {e}")
        except Exception:
            pass
