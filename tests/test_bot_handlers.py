from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session, select
from telegram import InlineKeyboardMarkup
from telegram.error import BadRequest

import bot.handlers as handlers
from app.modules.finanzas.models import Expense
from app.modules.finanzas.service import create_category

ALLOWED_USER_ID = 111  # matches TELEGRAM_ALLOWED_USER_IDS set in conftest


@pytest.fixture(autouse=True)
def bot_engine(engine, monkeypatch):
    # Handlers open their own Session(engine) over the module-level engine;
    # point it at the per-test in-memory engine.
    monkeypatch.setattr(handlers, "engine", engine)
    return engine


def make_update(text=None, user_id=ALLOWED_USER_ID):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.reply_chat_action = AsyncMock()
    return update


def make_context(args=None, user_data=None):
    context = MagicMock()
    context.args = args or []
    context.user_data = user_data if user_data is not None else {}
    return context


def make_callback_update(data, user_id=ALLOWED_USER_ID):
    update = make_update(user_id=user_id)
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update, query


class TestMessage:
    async def test_expense_with_known_category(self, session):
        cat = create_category(session, "Supermercado", "variable")
        update = make_update("mercadona 44")

        await handlers.message(update, make_context())

        reply = update.message.reply_text.call_args.args[0]
        assert "✓" in reply
        assert "mercadona" in reply
        assert "44.00€" in reply
        assert "Supermercado" in reply

        expenses = session.exec(select(Expense)).all()
        assert len(expenses) == 1
        assert expenses[0].amount == 44.0
        assert expenses[0].category_id == cat.id

    async def test_expense_without_category_asks(self, session):
        update = make_update("farmacia 12")
        context = make_context()

        await handlers.message(update, context)

        assert context.user_data["pending_expense"] == {
            "description": "farmacia", "amount": 12.0,
        }
        kwargs = update.message.reply_text.call_args.kwargs
        assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)
        assert "¿Categoría?" in update.message.reply_text.call_args.args[0]
        # no expense registered until the user picks a category
        assert session.exec(select(Expense)).all() == []

    async def test_free_text_saved_as_note(self, monkeypatch, tmp_path):
        monkeypatch.setattr(handlers.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
        update = make_update("hola qué tal")

        await handlers.message(update, make_context())

        reply = update.message.reply_text.call_args.args[0]
        assert "Nota guardada" in reply
        # Tags en su propia línea, separadas por salto en blanco (capitalizado / "sin tags")
        assert "\n\n🏷️" in reply
        # El eco (línea bajo el header) usa el texto real, no el filename slugificado
        preview_line = reply.split("\n")[1]
        assert "hola qué tal" in preview_line
        assert "-" not in preview_line
        assert list((tmp_path / "inbox").glob("*.md"))

    async def test_dot_prefix_short_note(self, monkeypatch, tmp_path):
        monkeypatch.setattr(handlers.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
        update = make_update(". comprar leche")

        await handlers.message(update, make_context())

        assert "Nota guardada" in update.message.reply_text.call_args.args[0]
        content = next((tmp_path / "inbox").glob("*.md")).read_text(encoding="utf-8")
        assert "comprar leche" in content

    async def test_short_unparseable_shows_help(self):
        update = make_update("hola")

        await handlers.message(update, make_context())

        assert "No entiendo" in update.message.reply_text.call_args.args[0]
        assert "/help" in update.message.reply_text.call_args.args[0]

    async def test_unauthorized_user_ignored(self):
        update = make_update("mercadona 44", user_id=999)

        await handlers.message(update, make_context())

        update.message.reply_text.assert_not_called()


class TestCallbackCategoria:
    async def test_registers_pending_expense(self, session):
        cat = create_category(session, "Salud", "variable")
        update, query = make_callback_update(f"cat:{cat.id}")
        context = make_context(user_data={
            "pending_expense": {"description": "farmacia", "amount": 12.0},
        })

        await handlers.callback_categoria(update, context)

        expenses = session.exec(select(Expense)).all()
        assert len(expenses) == 1
        assert expenses[0].category_id == cat.id
        assert "pending_expense" not in context.user_data
        assert "Salud" in query.edit_message_text.call_args.args[0]

    async def test_sin_categoria_option(self, session):
        update, query = make_callback_update("cat:0")
        context = make_context(user_data={
            "pending_expense": {"description": "algo", "amount": 5.0},
        })

        await handlers.callback_categoria(update, context)

        expenses = session.exec(select(Expense)).all()
        assert len(expenses) == 1
        assert expenses[0].category_id is None

    async def test_without_pending_expense(self):
        update, query = make_callback_update("cat:1")

        await handlers.callback_categoria(update, make_context())

        assert "Sin gasto pendiente" in query.edit_message_text.call_args.args[0]


class TestBorrar:
    async def test_cmd_borrar_asks_confirmation(self, session):
        e = Expense(amount=10.0, description="cine")
        session.add(e)
        session.commit()
        session.refresh(e)

        update = make_update()
        await handlers.cmd_borrar(update, make_context(args=[str(e.id)]))

        kwargs = update.message.reply_text.call_args.kwargs
        assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)

    async def test_cmd_borrar_requires_numeric_id(self):
        update = make_update()
        await handlers.cmd_borrar(update, make_context(args=["abc"]))
        assert "número" in update.message.reply_text.call_args.args[0]

    async def test_callback_borrar_deletes(self, session):
        e = Expense(amount=10.0)
        session.add(e)
        session.commit()
        session.refresh(e)

        update, query = make_callback_update(f"borrar:{e.id}")
        await handlers.callback_borrar(update, make_context())

        assert session.exec(select(Expense)).all() == []
        assert "eliminado" in query.edit_message_text.call_args.args[0]

    async def test_callback_borrar_cancel(self, session):
        e = Expense(amount=10.0)
        session.add(e)
        session.commit()

        update, query = make_callback_update("borrar:cancel")
        await handlers.callback_borrar(update, make_context())

        assert len(session.exec(select(Expense)).all()) == 1
        assert "Cancelado" in query.edit_message_text.call_args.args[0]


class TestGastos:
    async def test_empty(self):
        update = make_update()
        await handlers.cmd_gastos(update, make_context())
        assert "Sin gastos" in update.message.reply_text.call_args.args[0]

    async def test_lists_latest(self, session):
        session.add(Expense(amount=12.5, description="cine"))
        session.commit()

        update = make_update()
        await handlers.cmd_gastos(update, make_context())

        reply = update.message.reply_text.call_args.args[0]
        assert "Últimos gastos" in reply
        assert "12.50€" in reply
        assert "cine" in reply
        # /gastos no muestra id (para eso está /gastosid)
        assert "#" not in reply

    async def test_gastosid_shows_id(self, session):
        exp = Expense(amount=12.5, description="cine")
        session.add(exp)
        session.commit()
        session.refresh(exp)

        update = make_update()
        await handlers.cmd_gastosid(update, make_context())

        reply = update.message.reply_text.call_args.args[0]
        assert f"#{exp.id}" in reply
        assert "cine" in reply
        assert "/borrar" in reply


class TestVoiceMessage:
    async def test_voice_transcribed_and_saved(self, monkeypatch, tmp_path):
        monkeypatch.setattr(handlers.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))

        async def fake_download(path):
            Path(path).write_bytes(b"ogg")

        tg_file = MagicMock()
        tg_file.download_to_drive = fake_download
        monkeypatch.setattr(handlers, "transcribe", lambda p: "nota dictada por voz")

        update = make_update()
        update.message.voice = MagicMock(file_id="fid")
        context = make_context()
        context.bot.get_file = AsyncMock(return_value=tg_file)

        await handlers.voice_message(update, context)

        reply = update.message.reply_text.call_args.args[0]
        assert "Nota guardada (voz)" in reply
        assert list((tmp_path / "inbox").glob("*.md"))

    async def test_empty_transcription(self, monkeypatch):
        monkeypatch.setattr(handlers, "transcribe", lambda p: "   ")

        async def fake_download(path):
            Path(path).write_bytes(b"ogg")

        tg_file = MagicMock()
        tg_file.download_to_drive = fake_download
        update = make_update()
        update.message.voice = MagicMock(file_id="fid")
        context = make_context()
        context.bot.get_file = AsyncMock(return_value=tg_file)

        await handlers.voice_message(update, context)

        assert "no tenía texto" in update.message.reply_text.call_args.args[0]


class TestNoteRouting:
    def test_note_text_from_message(self):
        assert handlers.note_text_from_message(". idea") == "idea"
        assert handlers.note_text_from_message("varias palabras aquí") == "varias palabras aquí"
        assert handlers.note_text_from_message("hola") is None
        assert handlers.note_text_from_message(".") is None


class TestSafeReply:
    async def test_plain_text_sends_once(self):
        update = make_update()
        await handlers.safe_reply(update, "hola", parse_mode="Markdown")
        update.message.reply_text.assert_called_once()

    async def test_falls_back_to_plain_on_bad_markdown(self):
        update = make_update()
        update.message.reply_text = AsyncMock(
            side_effect=[BadRequest("Can't parse entities"), None]
        )
        await handlers.safe_reply(update, "roto *_[", parse_mode="Markdown")
        assert update.message.reply_text.call_count == 2
        # retry drops parse_mode so the text always reaches the user
        assert "parse_mode" not in update.message.reply_text.call_args.kwargs
        assert update.message.reply_text.call_args.args[0] == "roto *_["

    async def test_retry_keeps_reply_markup(self):
        update = make_update()
        update.message.reply_text = AsyncMock(
            side_effect=[BadRequest("Can't parse entities"), None]
        )
        markup = InlineKeyboardMarkup([])
        await handlers.safe_reply(update, "x", parse_mode="Markdown", reply_markup=markup)
        assert update.message.reply_text.call_args.kwargs["reply_markup"] is markup


class TestUnsupportedMessage:
    async def test_replies_with_hint(self):
        update = make_update()
        await handlers.unsupported_message(update, make_context())
        reply = update.message.reply_text.call_args.args[0]
        assert "voz" in reply.lower()

    async def test_unauthorized_ignored(self):
        update = make_update(user_id=999)
        await handlers.unsupported_message(update, make_context())
        update.message.reply_text.assert_not_called()


class TestOtherCommands:
    async def test_start_shows_welcome(self):
        update = make_update()
        await handlers.start(update, make_context())
        reply = update.message.reply_text.call_args.args[0]
        assert "SureHub" in reply
        assert "/help" in reply

    async def test_help_lists_commands(self):
        update = make_update()
        await handlers.cmd_help(update, make_context())
        reply = update.message.reply_text.call_args.args[0]
        assert "/gastos" in reply
        assert "/inbox" in reply
        assert "/recuerda" not in reply

    async def test_mes_without_categories(self):
        update = make_update()
        await handlers.cmd_mes(update, make_context())
        assert "Sin categorías" in update.message.reply_text.call_args.args[0]

    async def test_categorias_lists(self, session):
        create_category(session, "Ocio", "variable", estimate=50)
        update = make_update()
        await handlers.cmd_categorias(update, make_context())
        reply = update.message.reply_text.call_args.args[0]
        assert "Ocio" in reply
        assert "50€/mes" in reply

    async def test_analisis_asks_confirmation(self, monkeypatch):
        llm_mock = MagicMock(return_value="análisis mock")
        monkeypatch.setattr(handlers, "chat", llm_mock)

        update = make_update()
        await handlers.cmd_analisis(update, make_context())

        llm_mock.assert_not_called()
        reply = update.message.reply_text.call_args.args[0]
        assert "coste" in reply.lower()
        assert isinstance(update.message.reply_text.call_args.kwargs["reply_markup"], InlineKeyboardMarkup)

    async def test_analisis_confirm_calls_llm(self, session, monkeypatch):
        from app.modules.memoria.service import save_memory
        llm_mock = MagicMock(return_value="análisis mock")
        monkeypatch.setattr(handlers, "chat", llm_mock)
        save_memory(session, "le gusta el pádel")

        update, query = make_callback_update("analisis:confirm")
        context = make_context(user_data={"pending_analisis": "¿cómo voy?"})
        await handlers.callback_analisis(update, context)

        llm_mock.assert_called_once()
        memory_context = llm_mock.call_args.args[1]
        assert "le gusta el pádel" in memory_context
        assert llm_mock.call_args.args[0] == "¿cómo voy?"
        update.message.reply_text.assert_called_once_with("análisis mock", parse_mode="Markdown")

    async def test_analisis_cancel(self):
        update, query = make_callback_update("analisis:cancel")
        context = make_context(user_data={"pending_analisis": "pregunta"})
        await handlers.callback_analisis(update, context)

        assert context.user_data == {}
        assert "Cancelado" in query.edit_message_text.call_args.args[0]
