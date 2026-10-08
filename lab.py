import re
import sys
from dataclasses import dataclass

class ParseError(Exception):
    def __init__(self, message: str, line: int = 0, col: int = 0):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def __str__(self) -> str:
        if self.line:
            return f"{self.message} (рядок {self.line}, стовпець {self.col})"
        return self.message


KEYWORDS = {
    "CREATE", "INSERT", "PRINT_TREE", "CONTAINS", "SEARCH",
    "WHERE", "INTERSECTS", "LEFT_OF",
}

NUMBER_RE = re.compile(r"-?\d+")
IDENT_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*")
WORD_RE = re.compile(r"-?[A-Za-z0-9_]+")
WHITESPACE = " \t\r\n"


@dataclass
class Token:
    kind: str      # KEYWORD, IDENT, NUMBER, LBRACKET, RBRACKET, COMMA, END
    value: str
    line: int
    col: int


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i, line, col = 0, 1, 1
    n = len(text)

    while i < n:
        c = text[i]
        if c in WHITESPACE:
            if c == "\n":
                line, col = line + 1, 1
            else:
                col += 1
            i += 1
        elif c in "[],":
            kind = {"[": "LBRACKET", "]": "RBRACKET", ",": "COMMA"}[c]
            tokens.append(Token(kind, c, line, col))
            i += 1
            col += 1
        else:
            m = WORD_RE.match(text, i)
            if not m:
                raise ParseError(f"недопустимий символ '{c}'", line, col)
            word = m.group()
            if NUMBER_RE.fullmatch(word):
                kind = "NUMBER"
            elif IDENT_RE.fullmatch(word):
                kind = "KEYWORD" if word.upper() in KEYWORDS else "IDENT"
            else:
                raise ParseError(f"некоректна лексема '{word}'", line, col)
            tokens.append(Token(kind, word, line, col))
            i += len(word)
            col += len(word)

    tokens.append(Token("END", "", line, col))
    return tokens


@dataclass
class Interval:
    low: int
    high: int

    def __str__(self) -> str:
        return f"[{self.low}, {self.high}]"


@dataclass
class ContainsQuery:
    interval: Interval


@dataclass
class IntersectsQuery:
    interval: Interval


@dataclass
class LeftOfQuery:
    x: int


Query = ContainsQuery | IntersectsQuery | LeftOfQuery


@dataclass
class Create:
    name: str


@dataclass
class Insert:
    name: str
    interval: Interval


@dataclass
class PrintTree:
    name: str


@dataclass
class Contains:
    name: str
    interval: Interval


@dataclass
class Search:
    name: str
    query: Query | None = None


Command = Create | Insert | PrintTree | Contains | Search


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    @property
    def cur(self) -> Token:
        return self.tokens[self.pos]

    def error(self, message: str, tok: Token | None = None) -> ParseError:
        tok = tok or self.cur
        return ParseError(message, tok.line, tok.col)

    @staticmethod
    def describe(tok: Token) -> str:
        return "кінець команди" if tok.kind == "END" else f"'{tok.value}'"

    def advance(self) -> Token:
        tok = self.cur
        if tok.kind != "END":
            self.pos += 1
        return tok

    def expect_kind(self, kind: str, what: str) -> Token:
        if self.cur.kind != kind:
            raise self.error(f"очікувалось {what}, а знайдено {self.describe(self.cur)}")
        return self.advance()

    def expect_keyword(self, kw: str) -> Token:
        if self.cur.kind != "KEYWORD" or self.cur.value.upper() != kw:
            raise self.error(f"очікувалось ключове слово {kw}, а знайдено {self.describe(self.cur)}")
        return self.advance()

    def parse_name(self) -> str:
        tok = self.cur
        if tok.kind == "KEYWORD":
            raise self.error(f"ключове слово '{tok.value}' не може бути назвою множини")
        if tok.kind != "IDENT":
            raise self.error(
                f"очікувалась назва множини [a-zA-Z][a-zA-Z0-9_]*, а знайдено {self.describe(tok)}")
        self.advance()
        return tok.value

    def parse_number(self) -> int:
        return int(self.expect_kind("NUMBER", "ціле число").value)

    def parse_interval(self) -> Interval:
        self.expect_kind("LBRACKET", "'['")
        first = self.cur
        low = self.parse_number()
        self.expect_kind("COMMA", "','")
        high = self.parse_number()
        self.expect_kind("RBRACKET", "']'")
        if low > high:
            raise self.error(f"нижня границя ({low}) більша за верхню ({high})", first)
        return Interval(low, high)

    def parse_query(self) -> Query:
        tok = self.cur
        if tok.kind != "KEYWORD" or tok.value.upper() not in ("CONTAINS", "INTERSECTS", "LEFT_OF"):
            raise self.error(
                f"після WHERE очікувалось CONTAINS, INTERSECTS або LEFT_OF, а знайдено {self.describe(tok)}")
        self.advance()
        kw = tok.value.upper()
        if kw == "CONTAINS":
            return ContainsQuery(self.parse_interval())
        if kw == "INTERSECTS":
            return IntersectsQuery(self.parse_interval())
        return LeftOfQuery(self.parse_number())

    def parse_command(self) -> Command:
        tok = self.cur
        if tok.kind == "END":
            raise self.error("порожня команда")
        if tok.kind != "KEYWORD" or tok.value.upper() in ("WHERE", "INTERSECTS", "LEFT_OF"):
            raise self.error(f"невідома команда {self.describe(tok)}")
        self.advance()
        kw = tok.value.upper()

        if kw == "CREATE":
            cmd: Command = Create(self.parse_name())
        elif kw == "PRINT_TREE":
            cmd = PrintTree(self.parse_name())
        elif kw == "INSERT":
            cmd = Insert(self.parse_name(), self.parse_interval())
        elif kw == "CONTAINS":
            cmd = Contains(self.parse_name(), self.parse_interval())
        else:  # SEARCH
            name = self.parse_name()
            query = None
            if self.cur.kind != "END":
                self.expect_keyword("WHERE")
                query = self.parse_query()
            cmd = Search(name, query)

        if self.cur.kind != "END":
            raise self.error(f"зайві символи в кінці команди: {self.describe(self.cur)}")
        return cmd


def parse(text: str) -> Command:
    return Parser(tokenize(text)).parse_command()


HELP = """\
Доступні команди:
  CREATE set_name;
  INSERT set_name [l, h];
  PRINT_TREE set_name;
  CONTAINS set_name [l, h];
  SEARCH set_name;
  SEARCH set_name WHERE CONTAINS [L, H];
  SEARCH set_name WHERE INTERSECTS [L, H];
  SEARCH set_name WHERE LEFT_OF x;
Службові: help, exit (або quit, Ctrl+D)."""


def describe_command(cmd: Command) -> str:
    return f"OK: {cmd}"


def read_command(interactive: bool) -> str | None:
    parts: list[str] = []
    while True:
        prompt = "> " if not parts else "... "
        try:
            line = input(prompt if interactive else "")
        except EOFError:
            if parts and "".join(parts).strip():
                raise ParseError("команда має закінчуватись символом ';'")
            return None
        if not parts and line.strip().lower() in ("exit", "quit", "help"):
            return line.strip().lower()
        pos = line.find(";")
        if pos != -1:
            parts.append(line[:pos])
            return "\n".join(parts)
        parts.append(line)


def main() -> None:
    interactive = sys.stdin.isatty()
    if interactive:
        print("R-Tree sets console. Введіть 'help' для списку команд.")

    while True:
        try:
            raw = read_command(interactive)
        except ParseError as e:
            print(f"Синтаксична помилка: {e}", file=sys.stderr)
            break
        except KeyboardInterrupt:
            print()
            continue

        if raw is None or raw in ("exit", "quit"):
            break
        if raw == "help":
            print(HELP)
            continue
        try:
            print(describe_command(parse(raw)))
        except ParseError as e:
            print(f"Синтаксична помилка: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
