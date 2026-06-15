from bot.help_text import bot_commands


def test_bot_commands_registered():
    names = {c.command for c in bot_commands()}
    assert "help" in names
    assert "gastos" in names
    assert "nota" in names
    assert len(names) >= 10
