# coding: utf-8

import xml.etree.ElementTree as ET

class XmldocParser(object):
  def __init__(self, doctext):
    self.fulltext = doctext

  def parse(self):

    # Flatten any remark / summary,

    # c is inline code
    # code is code blocks

    # Argument-list nodes:
    # param, returns, typeparam, exception

    # Seealso specially handled

    # Special wrap
    spec = "<xmldoc>{}</xmldoc>".format(self.fulltext)
    root = ET.fromstring(spec)
    return self.process_node(root)

  def flatten_node(self, node):
    # print "Flattening " + node.tag
    parts = []
    arg_lists = []

    if node.text:
      parts.append(node.text.strip())
    for child in node:
      # If it's a parameter list node, skip for now
      if child.tag in ("param", "returns", "typeparam", "exception"):
        # Float these to the end
        arg_lists.append(child)
      else:
        parts.append(self.process_node(child))
      if child.tail:
        tail = child.tail.strip()
        if tail:
          parts.append(tail)
    if arg_lists:
      parts.append('\n')
    for special in arg_lists:
      parts.append('\n' + self.process_node(special))

    return parts

  def process_node(self, node):
    """Processes a special node into a string"""
    # Summary, remarks are just flattened
    if node.tag in ("summary", "remarks", "xmldoc", "value"):
      text = " ".join(self.flatten_node(node))
      if node.tag != "xmldoc" and not text[-1] == ".":
        text += "."
      return text

    if node.tag == "param":
      name = node.get("name", '')
      return ":param {}: {}".format(name, " ".join(self.flatten_node(node)))

    if node.tag == "returns":
      return ":returns: {}".format(" ".join(self.flatten_node(node)))

    return ET.tostring(node)


