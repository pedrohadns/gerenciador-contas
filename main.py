import webview
import os
import sys
from backend.api import BoletoAPI

if __name__ == '__main__':
    api = BoletoAPI()

    caminho_html = os.path.join(os.getcwd(), 'frontend', 'index.html')
    url = f'file://{caminho_html}'

    window = webview.create_window(
            'Gerenciador de boletos',
            url = url,
            js_api = api,
            width = 1024,
            height = 768
            )
    webview.start(debug=True)

def resource_path(relative_path):
    """ Retorna o caminho absoluto para o recurso, funcionando tanto em dev quanto no PyInstaller """
    try:
        # PyInstaller cria uma pasta temp e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
