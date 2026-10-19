"""dBase Revival by Jair Lima: utilitários de terminal."""
import os
import subprocess


def limpar_tela() -> None:
    """Limpa a tela sem passar texto por um shell (lista de argumentos, comando fixo)."""
    try:
        subprocess.run(["cmd", "/c", "cls"] if os.name == "nt" else ["clear"], check=False)
    except OSError:
        pass
