from unittest.mock import MagicMock, patch

from app.services.transcribe import transcribe


def test_transcribe_joins_segments():
    seg1 = MagicMock()
    seg1.text = " hola "
    seg2 = MagicMock()
    seg2.text = "mundo"
    model = MagicMock()
    model.transcribe.return_value = ([seg1, seg2], None)

    with patch("app.services.transcribe._model", return_value=model):
        assert transcribe("/tmp/x.ogg") == "hola mundo"
