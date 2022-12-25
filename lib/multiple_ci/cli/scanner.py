#!/bin/env python
from multiple_ci.scanner.scanner import Scanner

# TODO: CLI
def main():
    scanner = Scanner()
    scanner.init()
    scanner.scan()
