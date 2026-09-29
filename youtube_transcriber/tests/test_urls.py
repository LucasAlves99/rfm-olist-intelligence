import pytest

from yt_transcriber.errors import InvalidVideoReference
from yt_transcriber.urls import extract_video_id

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "ref",
    [
        VID,
        f"  {VID}  ",
        f"https://www.youtube.com/watch?v={VID}",
        f"https://www.youtube.com/watch?v={VID}&t=42s&list=PLabc",
        f"https://www.youtube.com/watch?feature=share&v={VID}",
        f"https://youtube.com/watch/?v={VID}",
        f"https://m.youtube.com/watch?v={VID}",
        f"https://music.youtube.com/watch?v={VID}",
        f"http://www.youtube.com/watch?v={VID}",
        f"www.youtube.com/watch?v={VID}",
        f"youtube.com/watch?v={VID}",
        f"https://youtu.be/{VID}",
        f"https://youtu.be/{VID}?t=10",
        f"https://www.youtube.com/shorts/{VID}",
        f"https://www.youtube.com/embed/{VID}",
        f"https://www.youtube.com/live/{VID}?feature=share",
        f"https://www.youtube.com/v/{VID}",
        f"https://www.youtube-nocookie.com/embed/{VID}",
    ],
)
def test_extracts_id(ref):
    assert extract_video_id(ref) == VID


@pytest.mark.parametrize(
    "ref",
    [
        "",
        "   ",
        "curto",
        "id-com-mais-de-onze-chars",
        "https://www.youtube.com/",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?v=curto",
        "https://www.youtube.com/playlist?list=PLabcdefghijk",
        "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv",
        # Host de outro domínio nunca vale, mesmo com um "ID" válido no caminho/consulta:
        f"https://evil.example.com/watch?v={VID}",
        f"https://youtube.com.evil.example/watch?v={VID}",
        f"https://notyoutube.com/embed/{VID}",
        f"https://evil.example/youtu.be/{VID}",
        # O ataque de verdade: host errado com o ID já como primeiro segmento do caminho.
        f"https://evil.example/{VID}",
        f"https://youtu.be.evil.example/{VID}",
        f"https://evil.example/embed/{VID}",
        f"https://evil.example/shorts/{VID}",
    ],
)
def test_rejects_non_video(ref):
    with pytest.raises(InvalidVideoReference):
        extract_video_id(ref)


def test_id_cannot_smuggle_path_characters():
    # O ID vira nome de arquivo: nada de separador de caminho passando pela validação.
    for bad in ("../../etc/pw", "a/b/c/d/e/f", "abc..def.gh"):
        with pytest.raises(InvalidVideoReference):
            extract_video_id(bad)
