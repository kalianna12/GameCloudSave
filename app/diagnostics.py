"""Bounded local diagnostics without request bodies or credentials."""
import logging,re,sys
from logging.handlers import RotatingFileHandler

class Redact(logging.Filter):
    def filter(self,record):
        text=record.getMessage()
        text=re.sub(r'(?i)(bearer\s+|sk-)[a-z0-9._-]+','[credential]',text)
        text=re.sub(r'(https?://)[^\s/@]+:[^\s/@]+@',r'\1[credential]@',text)
        text=re.sub(r'(https?://[^\s?]+)\?[^\s]+',r'\1?[query]',text)
        record.msg=text;record.args=()
        return True

def configure(root):
    directory=root/'logs';directory.mkdir(parents=True,exist_ok=True)
    logger=logging.getLogger('gamecloud');logger.setLevel(logging.WARNING)
    handler=RotatingFileHandler(directory/'app.log',maxBytes=512000,backupCount=2,encoding='utf-8')
    handler.addFilter(Redact());handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    def exception(kind,error,traceback):
        # Do not stringify arbitrary exceptions: they may contain external inputs.
        import traceback as tb
        logger.error('Unhandled %s\n%s',kind.__name__,''.join(tb.format_tb(traceback)))
        if sys.stderr:sys.__excepthook__(kind,error,traceback)
    sys.excepthook=exception
    return logger
