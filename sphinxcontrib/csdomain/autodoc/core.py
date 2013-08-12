# coding: utf-8
from ..parser import DefinitionError
import re

_newline_re = re.compile(r'[\n\r]')
_not_newline_re = re.compile(r'[^\n\r]*')
_whitespace_re = re.compile(r'\s+(?u)')

class CoreParser(object):
  def __init__(self, definition):
    self.definition = definition.strip()
    self.pos = 0
    self.end = len(self.definition)
    self.last_match = None
    self._previous_state = (0, None)

  def savepos(self):
    return (self.pos, self.last_match)

  def restorepos(self, state):
    (self.pos, self.last_match) = state

  def cur_line(self):
    self.match(_not_newline_re)
    value = self.matched_text
    self.backout()
    return value

  @property
  def line_no(self):
    return len(_newline_re.findall(self.definition[:self.pos]))+1

  def get_line(self, number= -1):
    if number < 0:
      return self.get_line(self.line_no)
    return self.definition.splitlines()[number-1]

  def current_line_start_pos(self):
    """Returns the positional index of the start of the current line"""
    # Walk backwards until at 0 or start of line
    spos = self.pos
    while spos >= 0:
      if _newline_re.match(self.definition[spos]):
        return spos+1
      spos -= 1

  def warn(self, message):
    print message

  def fail(self, msg):
      raise DefinitionError(
        'Invalid definition: {} [error at {}]\n  {}\n  {}^here'
          .format(msg, self.pos, self.definition, " "*(self.pos)))
  
  def skip_word(self, word):
    return self.match(re.compile(r'\b%s\b' % re.escape(word)))

  def skip(self, chars):
    return self.match(re.compile(re.escape(chars)))

  def skip_with_ws(self, chars):
    if self.skip(chars):
      self.skip_ws()
      return True
    return False

  def skip_ws(self):
    return self.match(_whitespace_re)

  def skip_word_and_ws(self, word):
    if self.skip_word(word):
      self.skip_ws()
      return True
    return False

  def skip_to_char(self, char):
    assert len(char) == 1
    self.match(re.compile('[^{}]*'.format(char)))
    value = self.matched_text
    self.skip_ws()
    return value

  def skip_to_any_char(self, chars):
    self.match(re.compile('[^{}]*'.format(re.escape(chars))))
    value = self.matched_text
    self.skip_ws()
    return value

  def skip_to_eol(self):
    self.match(_not_newline_re)
    value = self.matched_text
    self.skip_ws()
    return value  

  def skip_single_eol(self):
    if not self.match(_not_newline_re):
      return None
    return self.matched_text
    

  def backout(self):
    """Resets the last match"""
    self.pos, self.last_match = self._previous_state

  def match(self, regex):
    match = regex.match(self.definition, self.pos)
    if match is not None:
      self._previous_state = (self.pos, self.last_match)
      self.pos = match.end()
      self.last_match = match
      return True
    return False

  def pop_char(self):
    if self.eof:
      return None
    ch = self.definition[self.pos]
    self.pos += 1
    return ch

  @property
  def next_char(self):
    if not self.eof:
      return self.definition[self.pos]
  
  @property
  def matched_text(self):
    if self.last_match is not None:
      return self.last_match.group()

  @property
  def eof(self):
      return self.pos >= self.end

  def opt(self, parser):
    state = self.savepos()
    try:
      return parser()
    except DefinitionError:
      self.restorepos(state)
      return None

  def first_of(self, parsers, msg=None):
    for parser in parsers:
      val = self.opt(parser)
      if val:
        return val
    if msg:
      raise DefinitionError(msg)
    else:
      raise DefinitionError("Could not resolve any parser")


