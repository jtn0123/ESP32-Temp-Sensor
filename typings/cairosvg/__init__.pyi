from typing import IO

def svg2png(
    url: str | None = ...,
    file_obj: IO[bytes] | None = ...,
    bytestring: bytes | bytearray | memoryview | None = ...,
    write_to: IO[bytes] | str | None = ...,
    dpi: float | int = ...,
    scale: float | None = ...,
    parent_width: int | float | None = ...,
    parent_height: int | float | None = ...,
    output_width: int | None = ...,
    output_height: int | None = ...,
    background_color: str | None = ...,
    unsafe: bool | None = ...,
) -> bytes: ...


