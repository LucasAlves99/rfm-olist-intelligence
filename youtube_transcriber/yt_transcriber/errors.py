"""Erros da ferramenta. Todos herdam de TranscriberError para a CLI tratá-los num só lugar."""


class TranscriberError(Exception):
    """Base de todos os erros esperados (mensagem já pronta para o usuário)."""


class InvalidVideoReference(TranscriberError):
    """A URL ou o ID informado não aponta para um vídeo do YouTube."""


class NoCaptionsAvailable(TranscriberError):
    """O vídeo não tem legenda utilizável. É o único erro que aciona o plano B (Whisper)."""


class VideoNotAccessible(TranscriberError):
    """Vídeo privado, removido, restrito por idade, bloqueado na região etc."""


class RequestBlockedError(TranscriberError):
    """O YouTube recusou a requisição (comum em IPs de nuvem/datacenter)."""


class MissingDependency(TranscriberError):
    """Falta um pacote opcional (yt-dlp / faster-whisper) necessário para o Whisper."""


class NetworkError(TranscriberError):
    """Não foi possível falar com o YouTube (sem internet, DNS, proxy, timeout)."""
