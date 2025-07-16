import unittest
from unittest.mock import patch, MagicMock
from gerar_enviar_clipping import (
    buscar_termo_no_querido_diario,
    gerar_html_resultado,
    gerar_corpo_email,
    enviar_email
)

class TestClipping(unittest.TestCase):

    @patch("gerar_enviar_clipping.requests.get")
    def test_buscar_termo_no_querido_diario_sucesso(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "total_gazettes": 1,
            "gazettes": [{"excerpts": ["teste"], "territory_name": "Teste", "url": "http://exemplo.com"}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = buscar_termo_no_querido_diario("teste")
        self.assertEqual(result["total_gazettes"], 1)

    @patch("gerar_enviar_clipping.requests.get")
    def test_buscar_termo_com_erro_na_requisicao(self, mock_get):
        mock_get.side_effect = Exception("Erro de rede")
        result = buscar_termo_no_querido_diario("qualquer")
        self.assertEqual(result["total_gazettes"], 0)
        self.assertEqual(result["gazettes"], [])

    @patch("gerar_enviar_clipping.requests.get")
    def test_buscar_termo_sem_resultado(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"total_gazettes": 0, "gazettes": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = buscar_termo_no_querido_diario("sem_resultado")
        self.assertEqual(result["total_gazettes"], 0)
        self.assertEqual(result["gazettes"], [])

    def test_gerar_html_resultado_sem_excerpt(self):
        resp = {
            "total_gazettes": 1,
            "gazettes": [
                {
                    "territory_name": "Cidade Y",
                    "url": "http://cidadey.com",
                    "excerpts": []
                }
            ]
        }
        html = gerar_html_resultado("termo_teste", resp)
        self.assertEqual(html, "")

    @patch("gerar_enviar_clipping.smtplib.SMTP_SSL")
    def test_enviar_email(self, mock_smtp):
        corpo = "<html><body>Teste</body></html>"
        enviar_email("Assunto Teste", corpo, ["dest@teste.com"])

        mock_smtp.assert_called_with("smtp.gmail.com", 465)
        instance = mock_smtp.return_value.__enter__.return_value
        instance.login.assert_called()
        instance.sendmail.assert_called()

if __name__ == '__main__':
    unittest.main()