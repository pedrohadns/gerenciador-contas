import webview
import os
import sys
from backend.api import BoletoAPI

def resource_path(relative_path):
    """ Retorna o caminho absoluto para o recurso, funcionando tanto em dev quanto no PyInstaller """
    try:
        # PyInstaller cria uma pasta temp e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

if __name__ == '__main__':
    api = BoletoAPI()

    arquivo_html = resource_path('index.html')

    window = webview.create_window(
            'Gestão',
            url=arquivo_html,
            js_api=api,
            width=1200, height=800
            )
    webview.start()
