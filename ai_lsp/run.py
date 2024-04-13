from .logging import log
from .server import AILanguageServer

if __name__ == "__main__":
    try:
        server = AILanguageServer.from_config()
        server.start_io()
    except Exception as e:
        log(e)
        raise e
