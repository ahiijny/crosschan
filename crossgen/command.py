import logging
import argparse
import sys

from crossgen import walker
from crossgen import pretty

# Helper functions

def create_crosswords(words, max=100, batch=5, debug=False, progress_callback=None):
    """progress_callback should be of the form `lambda num_crosswords : int`

    Returns a list of the form (score, crossword_grid).
    """
    # debourg

    if debug:
        import logging
        logging.basicConfig(level=logging.info)

    # batch is at most max

    if batch > max:
        batch = max

    # create

    crosswords = [] # list of (score, crossword_grid) instances
    try:
        print("Press Ctrl+C to stop at any time", file=sys.stderr)
        while max is None or len(crosswords) < max:
            for crossword in walker.generate_crosswords(words, max=batch):
                print(".", end="", file=sys.stderr, flush=True)
                crosswords.append((pretty.be_judgmental(crossword), crossword))
                if progress_callback is not None:
                    progress_callback(len(crosswords))
                if len(crosswords) == max:
                    break
    except KeyboardInterrupt: # graceful interrupt
        print(f"\ngenerated {len(crosswords)} crosswords", file=sys.stderr)

    # sort results in descending order by score

    crosswords = sorted(crosswords, key=lambda x: x[0], reverse=True)

    return crosswords

# Argparse stuff

class main:
    command_names = [
        "test",
        "create",
    ]

    def run(self, argv):
        parser = argparse.ArgumentParser(description="Crosswords",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        parser.add_argument("command", help="subcommand to run")
        subparsers = parser.add_subparsers(metavar="", dest="command")
        self.add_subparsers(subparsers)

        logging.basicConfig(level=logging.INFO)
        logging.debug('Started')

        args = parser.parse_args(argv)
        exit_code = 0
        if hasattr(args, "func"):
            exit_code = args.func(args)
        else:
            parser.print_help()
        
        logging.debug('Finished')
        sys.exit(exit_code)

    def add_subparsers(self, subparsers):
        """Add a subparser for each command in command_names.

        Assumes that the command objects follow the given interface:
        
        class cmd:
            + build_parser(self, subparser):
                adds the appropriate command line options to the given argparser
            + run(self, args): exit_code
                runs the command, given the argparse.Namespace args object
                can return exit code or not return anything at all (which is the same as returning 0)
        """
        for command_name in main.command_names:
            command = globals()[command_name.replace("-", "_")]()
            description = command.run.__doc__
            help = description.split("\n", 1)[0]
            subparser = subparsers.add_parser(command_name, description=description, help=help,
                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
            subparser.set_defaults(func=command.run)
            command.build_parser(subparser)

class test:
    def build_parser(self, subparser):
        subparser.add_argument("--option", metavar="VALUE", default="123456", help="description")

    def run(self, args):
        """This doesn't do anything"""
        print(args)

class create:
    def build_parser(self, subparser):
        subparser.add_argument("-i", "--from-file", metavar="PATH", default="-", help="file from which to read newline-separated words (use '-' to indicate stdin)")
        subparser.add_argument("--no-preprocess", action="store_true", help="turn off default preprocessing, which folds all words to uppercase and removes spaces")
        subparser.add_argument("-o", metavar="PATH", default="crosswords.html", help="output results to this path (will add a sequential number to path if file already exists)")
        subparser.add_argument("--overwrite", action="store_true", help="overwrite existing output file")
        # subparser.add_argument("-l", metavar="PATH", default="crosswords.log", help="output log to this path") # TODO
        subparser.add_argument("-x", "--max", metavar="MAX", default=100, type=int, help="output at most this many crosswords")
        subparser.add_argument("-d", "--debug", action="store_true", help="print debug stuff")
        subparser.add_argument("-b", "--batch", metavar="INT", default=5, type=int, help="because it's DFS, results don't really show that much diversity; so, this just tells the program to restart from scratch after every X crosswords generated")

    def run(self, args):
        """Read in words from stdout, terminated with an empty newline, and then generate crosswords.
        
        Output is in plain text format."""

        # input stream
        infile = sys.stdin
        inpath = args.from_file
        if inpath != "-":
            try:
                infile = open(inpath, "r")
            except IOError:
                print(f"could not open file {infile}")
                return 1
        else:
            print("Please input a newline separated list of words, terminated with an empty line:")

        # pretty output stream
        outfile = sys.stdout
        if not args.o.endswith(".html"):
            args.o += ".html"
        outpath = args.o

        if outpath is not None:
            success = False
            counter = 1
            while not success:
                try:
                    if args.overwrite:
                        outfile = open(outpath, "w", encoding="utf-8")
                        break
                    else:
                        temp_outfile = open(outpath, "a+", encoding="utf-8")
                        length = temp_outfile.tell()
                        if length > 0: # file already exists
                            outpath = args.o.replace(".html", "-" + str(counter) + ".html")
                            counter += 1
                        else:
                            outfile = temp_outfile
                            success = True
                except IOError:
                    print(f"could not open outfile {outpath}", file=sys.stderr)
            print(f"(The new crosswords will be saved to {outpath})", file=sys.stderr)

        # input

        words = []

        for word in infile:
            word = word.strip()
            if not args.no_preprocess:
                word = word.upper()
                word = word.replace(" ", "")
            if len(word) == 0:
                break
            words.append(word)

        # generate crosswords

        crosswords = create_crosswords(words=words, max=args.max, batch=args.batch, debug=args.debug)

        # print results
        
        print("", file=sys.stderr)

        for i, (score, crossword) in enumerate(crosswords):
            print(f"===CROSSWORD {i+1}, score:{score:.2f}===")
            print(crossword)
            print("===END===")
            print()

        pretty_printer = pretty.HtmlGridPrinter(outfile)
        pretty_printer.print_crosswords(crosswords)
