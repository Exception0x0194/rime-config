import io
import struct

from typing import List, Tuple


class BufferedIOWrapper:
    def __init__(self, bufferedReader: io.BufferedIOBase):
        self._buffer = bufferedReader

    def read_uint16(self) -> int:
        buffer = self._buffer.read(2)
        if buffer:
            return struct.unpack('<H', buffer)[0]
        else:
            return 0

    def read_uint32(self) -> int:
        return struct.unpack('<I', self._buffer.read(4))[0]

    def read_str(self) -> str:
        return ''.join(
            chr(struct.unpack('<H', self._buffer.read(2))[0])
            for i in range(int(self.read_uint16() / 2)))

    def seek(self, offset):
        self._buffer.seek(offset)

    def tell(self) -> int:
        return self._buffer.tell()

    def skip(self, offset):
        self._buffer.seek(offset, 1)

    def skip_uint16(self):
        self.skip(2)


class Scel:
    PINYIN_START = 0x1544
    CHAR_START = 0x2628

    def __init__(self, bufferedReader: io.BufferedIOBase):
        self._buffer = BufferedIOWrapper(bufferedReader)
        self._table = []

    def _read_pinyin_palette(self) -> List[str]:
        pinyin_palette = []
        self._buffer.seek(self.PINYIN_START)
        while self._buffer.tell() < self.CHAR_START:
            # skipped index, doesn't need.
            self._buffer.skip_uint16()
            pinyin_palette.append(self._buffer.read_str())

        return pinyin_palette

    def _read_pinyin(self, pinyin_palette: List[str]) -> str:
        try:
            return ' '.join(pinyin_palette[self._buffer.read_uint16()]
                            for i in range(int(self._buffer.read_uint16() /
                                               2)))
        except IndexError:
            return ''

    def _read_table(self,
                    pinyin_palette: List[str]) -> List[Tuple[str, str, int]]:
        table = []
        self._buffer.seek(self.CHAR_START)
        while word_count := self._buffer.read_uint16():
            pinyin = self._read_pinyin(pinyin_palette)
            if not pinyin:
                break
            for _ in range(word_count):
                phrase = self._buffer.read_str()
                # usually 10, at least 4 bytes after this is the order of the phrase (uint32), doesn't seen to matter.
                skip_length = self._buffer.read_uint16()
                order = self._buffer.read_uint32()
                self._buffer.skip(skip_length - 4)

                table.append((phrase, pinyin, order))

        table.sort(key=lambda x: x[2])
        return table

    def get_table(self):
        if not self._table:
            pinyin_palette = self._read_pinyin_palette()
            self._table = self._read_table(pinyin_palette)

        return list(map(lambda x: x[:2], self._table))


class RimeWriter:
    def __init__(self, table: List[Tuple[str, str]], name: str, version: str):
        self._table = table
        self._name = name
        self._version = version

    def write(self, file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f'''---
name: {self._name}
version: "{self._version}"
sort: by_weight
use_preset_vocabulary: false
...
''')
            for i in self._table:
                f.write('\t'.join(i) + '\t1\n')


def scel2rime(scel_path: str, rime_path: str, rime_name: str,
              rime_version: str):
    scel_file = open(scel_path, 'rb')
    scel = Scel(scel_file)
    rime_writer = RimeWriter(scel.get_table(), rime_name, rime_version)
    scel_file.close()
    rime_writer.write(rime_path)
