from __future__ import print_function

import os
import sys
import logging
import cPickle as pickle
import curses
import pprint

try:
    import pygments
    import pygments.lexers
    import pygments.formatters
    have_pygments = True
except:
    have_pygments = False

from collections import defaultdict
from termcolor import colored

from comms import *

log = logging.getLogger('voltron')

ADDR_FORMAT_128 = '0x{0:0=32X}'
ADDR_FORMAT_64 = '0x{0:0=16X}'
ADDR_FORMAT_32 = '0x{0:0=8X}'
ADDR_FORMAT_16 = '0x{0:0=4X}'
SHORT_ADDR_FORMAT_128 = '{0:0=32X}'
SHORT_ADDR_FORMAT_64 = '{0:0=16X}'
SHORT_ADDR_FORMAT_32 = '{0:0=8X}'
SHORT_ADDR_FORMAT_16 = '{0:0=4X}'

# Parent class for all views
class VoltronView (object):
    BASE_DEFAULT_CONFIG = {
        "update_on": "stop",
        "clear": True,
        "header": {
            "show":         True,
            "pad":          " ",
            "colour":       "blue",
            "bg_colour":    "grey",
            "attrs":        [],
            "label_left": {
                "name":         "info",
                "colour":       "blue",
                "bg_colour":    "grey",
                "attrs":        []
            },
            "label_right": {
                "name":         "title",
                "colour":       "blue",
                "bg_colour":    "grey",
                "attrs":        ["bold"]
            }
        },
        "footer": {
            "show":         True,
            "pad":          " ",
            "colour":       "blue",
            "bg_colour":    "grey",
            "attrs":        [],
            "label_left": {
                "name":         None,
                "colour":       "blue",
                "bg_colour":    "grey",
                "attrs":        []
            },
            "label_right": {
                "name":         None,
                "colour":       "blue",
                "bg_colour":    "grey",
                "attrs":        ["bold"],
            }
        }
    }
    VIEW_DEFAULT_CONFIG = {}

    @classmethod
    def add_generic_arguments(cls, sp):
        sp.add_argument('--show-header', '-e', dest="header", action='store_true', help='show header', default=None)
        sp.add_argument('--hide-header', '-E', dest="header", action='store_false', help='hide header')
        sp.add_argument('--show-footer', '-f', dest="footer", action='store_true', help='show footer', default=None)
        sp.add_argument('--hide-footer', '-F', dest="footer", action='store_false', help='hide footer')
        sp.add_argument('--name', '-n', action='store', help='named configuration to use', default=None)

    def __init__(self, args={}, loaded_config={}):
        log.debug('Loading view: ' + self.__class__.__name__)
        self.client = None
        self.args = args
        self.loaded_config = loaded_config

        # Commonly set by render method for header and footer formatting
        self.title = ''
        self.info = ''

        # Build configuration
        self.build_config()

        log.debug("View config: " + pprint.pformat(self.config))
        log.debug("Args: " + str(self.args))

        # Let subclass do any setup it needs to do
        self.setup()

        # Override settings from command line args
        if self.args.header != None:
            self.config['header']['show'] = self.args.header
        if self.args.footer != None:
            self.config['footer']['show'] = self.args.footer

        # Initialise window
        self.init_window()        

        # Connect to server
        self.connect()

    def build_config(self):
        # Start with base defaults
        self.config = self.BASE_DEFAULT_CONFIG

        # Add view-specific defaults
        merge(self.VIEW_DEFAULT_CONFIG, self.config)

        # Add all_views config from config file
        if self.loaded_config.has_key('view') and self.loaded_config['view'].has_key('all_views'):
            merge(self.loaded_config['view']['all_views'], self.config)

        # Add view-specific config from config file
        name = self.config['type']+'_view'
        if self.loaded_config.has_key('view') and self.loaded_config['view'].has_key(name):
            merge(self.loaded_config['view'][name], self.config)

        # Add named config
        if self.args.name != None:
            merge(self.loaded_config[self.args.name], self.config)

        # Apply view-specific command-line args
        self.apply_cli_config()

    def apply_cli_config(self):
        if self.args.header != None:
            self.config['header']['show'] = self.args.header
        if self.args.footer != None:
            self.config['footer']['show'] = self.args.footer

    def setup(self):
        log.debug('Base view class setup')

    def connect(self):
        try:
            self.client = Client(view=self, config=self.config)
            self.client.register()
        except Exception as e:
            log.error('Exception connecting: ' + str(e))
            raise e

    def run(self):
        os.system('clear')
        log.info('Waiting for an update from the debugger')
        asyncore.loop()

    def render(self, msg=None):
        log.warning('Might wanna implement render() in this view eh')

    def hexdump(self, src, length=16, sep='.', offset=0):
        FILTER = ''.join([(len(repr(chr(x))) == 3) and chr(x) or sep for x in range(256)])
        lines = []
        for c in xrange(0, len(src), length):
            chars = src[c:c+length]
            hex = ' '.join(["%02X" % ord(x) for x in chars])
            if len(hex) > 24:
                hex = "%s %s" % (hex[:24], hex[24:])
            printable = ''.join(["%s" % ((ord(x) <= 127 and FILTER[ord(x)]) or sep) for x in chars])
            lines.append("%s:  %-*s  |%s|\n" % (ADDR_FORMAT_64.format(offset+c), length*3, hex, printable))
        return ''.join(lines).strip()

    def format_header(self):
        height, width = self.window_size()

        # Get values for labels
        l = getattr(self, self.config['header']['label_left']['name']) if self.config['header']['label_left']['name'] != None else ''
        r = getattr(self, self.config['header']['label_right']['name']) if self.config['header']['label_right']['name'] != None else ''
        p = self.config['header']['pad']
        llen = len(l)
        rlen = len(r)

        # Add colour
        l = colored(l, self.config['header']['label_left']['colour'], 'on_' + self.config['header']['label_left']['bg_colour'], self.config['header']['label_left']['attrs'])
        r = colored(r, self.config['header']['label_right']['colour'], 'on_' + self.config['header']['label_right']['bg_colour'], self.config['header']['label_right']['attrs'])
        p = colored(p, self.config['header']['colour'], 'on_' + self.config['header']['bg_colour'], self.config['header']['attrs'])

        # Build header
        header = l + (width - llen - rlen)*p + r
        
        return header

    def format_footer(self):
        height, width = self.window_size()

        # Get values for labels
        l = getattr(self, self.config['footer']['label_left']['name']) if self.config['footer']['label_left']['name'] != None else ''
        r = getattr(self, self.config['footer']['label_right']['name']) if self.config['footer']['label_right']['name'] != None else ''
        p = self.config['footer']['pad']
        llen = len(l)
        rlen = len(r)

        # Add colour
        l = colored(l, self.config['footer']['label_left']['colour'], 'on_' + self.config['footer']['label_left']['bg_colour'], self.config['footer']['label_left']['attrs'])
        r = colored(r, self.config['footer']['label_right']['colour'], 'on_' + self.config['footer']['label_right']['bg_colour'], self.config['footer']['label_right']['attrs'])
        p = colored(p, self.config['footer']['colour'], 'on_' + self.config['footer']['bg_colour'], self.config['footer']['attrs'])

        # Build header and footer
        footer = l + (width - llen - rlen)*p + r
        
        return footer


class TerminalView (VoltronView):
    def init_window(self):
        # Hide cursor
        os.system('tput civis')

    def cleanup(self):
        log.debug('Cleaning up view')
        os.system('tput cnorm')

    def clear(self):
        os.system('clear')

    def render(self, msg=None):
        self.clear()
        if self.config['header']['show']:
            print(self.format_header())
        print(self.body, end='')
        if self.config['footer']['show']:
            print('\n' + self.format_footer(), end='')
        sys.stdout.flush()

    def window_size(self):
        height, width = os.popen('stty size').read().split()
        height = int(height)
        width = int(width)
        return (height, width)

    def body_height(self):
        height, width = self.window_size()
        if self.config['header']['show']:
            height -= 1
        if self.config['footer']['show']:
            height -= 1
        return height


class CursesView (VoltronView):
    def init_window(self):
        self.screen = curses.initscr()
        self.screen.border(0)

    def cleanup(self):
        curses.endwin()

    def render(self, msg=None):
        self.screen.clear()
        y = 0
        if self.config['header']['show']:
            self.screen.addstr(0, 0, self.header)
            y = 1
        self.screen.addstr(0, y, self.body)
        self.screen.refresh()

    def clear(self):
        # Clear the window - this sucks, should probably do it with ncurses at some stage
        os.system('clear')

    def window_size(self):
        # Get terminal size - this also sucks, but curses sucks more
        height, width = os.popen('stty size').read().split()
        height = int(height)
        width = int(width)
        return (height, width)

    def body_height(self):
        height, width = self.window_size()
        if self.config['header']['show']:
            height -= 1
        if self.config['footer']['show']:
            height -= 1
        return height


# Class to actually render the view
class RegisterView (TerminalView):
    VIEW_DEFAULT_CONFIG = {
        'type': 'register',
        'format_defaults': {
            'label_format':     '{0}:',
            'label_func':       'str.upper',
            'label_colour':     'green',
            'label_colour_en':  True,
            'value_format':     SHORT_ADDR_FORMAT_64,
            'value_func':       None,
            'value_colour':     'grey',
            'value_colour_mod': 'red',
            'value_colour_en':  True
        },
        'sections': ['general'],
        'orientation': 'vertical'
    }
    FORMAT_INFO = {
        'x64': [
            {
                'regs':             ['rax','rbx','rcx','rdx','rbp','rsp','rdi','rsi','rip',
                                     'r8','r9','r10','r11','r12','r13','r14','r15'],
                'label_format':     '{0:3s}:',
                'category':         'general',
            },
            {
                'regs':             ['cs','ds','es','fs','gs','ss'],
                'value_format':     SHORT_ADDR_FORMAT_16,
                'category':         'general',
            },
            {
                'regs':             ['rflags'],
                'value_format':     '{}',
                'value_func':       'self.format_flags',
                'value_colour_en':  False,
                'category':         'general',
            },
            {
                'regs':             ['xmm0','xmm1','xmm2','xmm3','xmm4','xmm5','xmm6','xmm7','xmm8',
                                     'xmm9','xmm10','xmm11','xmm12','xmm13','xmm14','xmm15'],
                'value_format':     SHORT_ADDR_FORMAT_128,
                'value_func':       'self.format_xmm',
                'category':         'sse',
            },
            {
                'regs':             ['st0','st1','st2','st3','st4','st5','st6','st7'],
                'value_format':     '{0:0=20X}',
                'value_func':       'self.format_fpu',
                'category':         'fpu',
            },
        ],
        'x86': [
            {
                'regs':             ['eax','ebx','ecx','edx','ebp','esp','edi','esi','eip'],
                'label_format':     '{0:3s}:',
                'value_format':     SHORT_ADDR_FORMAT_32,
                'category':         'general',
            },
            {
                'regs':             ['cs','ds','es','fs','gs','ss'],
                'value_format':     SHORT_ADDR_FORMAT_16,
                'category':         'general',
            },
            {
                'regs':             ['eflags'],
                'value_format':     '{}',
                'value_func':       'self.format_flags',
                'value_colour_en':  False,
                'category':         'general',
            },
            {
                'regs':             ['xmm0','xmm1','xmm2','xmm3','xmm4','xmm5','xmm6','xmm7'],
                'value_format':     None,
                'value_func':       'self.format_xmm',
                'category':         'sse',
            },
            {
                'regs':             ['st0','st1','st2','st3','st4','st5','st6','st7'],
                'value_format':     '{0:0=20X}',
                'value_func':       'self.format_fpu',
                'category':         'fpu',
            },
        ],
        'arm': [
        ]
    }
    TEMPLATES = {
        'x64': {
            'horizontal': {
                'general': (
                    "{raxl} {rax}  {rbxl} {rbx}  {rbpl} {rbp}  {rspl} {rsp}  {rflags}\n"
                    "{rdil} {rdi}  {rsil} {rsi}  {rdxl} {rdx}  {rcxl} {rcx}  {ripl} {rip}\n"
                    "{r8l} {r8}  {r9l} {r9}  {r10l} {r10}  {r11l} {r11}  {r12l} {r12}\n"
                    "{r13l} {r13}  {r14l} {r14}  {r15l} {r15}\n"
                    "{csl} {cs}  {dsl} {ds}  {esl} {es}  {fsl} {fs}  {gsl} {gs}  {ssl} {ss}"
                ),
                'sse': (
                    "{xmm0l}  {xmm0} {xmm1l}  {xmm1} {xmm2l}  {xmm2}\n"
                    "{xmm3l}  {xmm3} {xmm4l}  {xmm4} {xmm5l}  {xmm5}\n"
                    "{xmm6l}  {xmm6} {xmm7l}  {xmm7} {xmm8l}  {xmm8}\n"
                    "{xmm9l}  {xmm9} {xmm10l} {xmm10} {xmm11l} {xmm11}\n"
                    "{xmm12l} {xmm12} {xmm13l} {xmm13} {xmm14l} {xmm14}\n"
                    "{xmm15l} {xmm15}\n"
                ),
                'fpu': (
                    "{st0l} {st0} {st1l} {st1} {st2l} {st2} {st3l} {st2}\n"
                    "{st4l} {st4} {st5l} {st5} {st6l} {st6} {st7l} {st7}\n"
                )
            },
            'vertical': {
                'general': (
                    "{rflags}\n"
                    "{ripl} {rip}\n"
                    "{raxl} {rax}\n{rbxl} {rbx}\n{rbpl} {rbp}\n{rspl} {rsp}\n"
                    "{rdil} {rdi}\n{rsil} {rsi}\n{rdxl} {rdx}\n{rcxl} {rcx}\n"
                    "{r8l} {r8}\n{r9l} {r9}\n{r10l} {r10}\n{r11l} {r11}\n{r12l} {r12}\n"
                    "{r13l} {r13}\n{r14l} {r14}\n{r15l} {r15}\n"
                    "{csl}  {cs}  {dsl}  {ds}\n{esl}  {es}  {fsl}  {fs}\n{gsl}  {gs}  {ssl}  {ss}"
                ),
                'sse': (
                    "{xmm0l}  {xmm0}\n{xmm1l}  {xmm1}\n{xmm2l}  {xmm2}\n{xmm3l}  {xmm3}\n"
                    "{xmm4l}  {xmm4}\n{xmm5l}  {xmm5}\n{xmm6l}  {xmm6}\n{xmm7l}  {xmm7}\n"
                    "{xmm8l}  {xmm8}\n{xmm9l}  {xmm9}\n{xmm10l} {xmm10}\n{xmm11l} {xmm11}\n"
                    "{xmm12l} {xmm12}\n{xmm13l} {xmm13}\n{xmm14l} {xmm14}\n{xmm15l} {xmm15}"
                ),
                'fpu': (
                    "{st0l} {st0}\n{st1l} {st1}\n{st2l} {st2}\n{st3l} {st2}\n"
                    "{st4l} {st4}\n{st5l} {st5}\n{st6l} {st6}\n{st7l} {st7}\n"
                )
            }
        },
        'x86': {
            'horizontal': {
                'general': (
                    "{eaxl} {eax}  {ebxl} {ebx}  {ebpl} {ebp}  {espl} {esp}  {eflags}\n"
                    "{edil} {edi}  {esil} {esi}  {edxl} {edx}  {ecxl} {ecx}  {eipl} {eip}\n"
                    "{csl} {cs}  {dsl} {ds}  {esl} {es}  {fsl} {fs}  {gsl} {gs}  {ssl} {ss}"
                ),
                'sse': (
                    "{xmm0l}  {xmm0} {xmm1l}  {xmm1} {xmm2l}  {xmm2}\n"
                    "{xmm3l}  {xmm3} {xmm4l}  {xmm4} {xmm5l}  {xmm5}\n"
                    "{xmm6l}  {xmm6} {xmm7l}"
                ),
                'fpu': (
                    "{st0l} {st0} {st1l} {st1} {st2l} {st2} {st3l} {st2}\n"
                    "{st4l} {st4} {st5l} {st5} {st6l} {st6} {st7l} {st7}\n"
                )
            },
            'vertical': {
                'general': (
                    "{eflags}\n"
                    "{eipl} {eip}\n"
                    "{eaxl} {eax}\n{ebxl} {ebx}\n{ebpl} {ebp}\n{espl} {esp}\n"
                    "{edil} {edi}\n{esil} {esi}\n{edxl} {edx}\n{ecxl} {ecx}\n"
                    "{csl}  {cs}  {dsl}  {ds}\n{esl}  {es}  {fsl}  {fs}\n{gsl}  {gs}  {ssl}  {ss}"
                ),
                'sse': (
                    "{xmm0l}  {xmm0}\n{xmm1l}  {xmm1}\n{xmm2l}  {xmm2}\n{xmm3l}  {xmm3}\n"
                    "{xmm4l}  {xmm4}\n{xmm5l}  {xmm5}\n{xmm6l}  {xmm6}\n{xmm7l}  {xmm7}\n"
                ),
                'fpu': (
                    "{st0l} {st0}\n{st1l} {st1}\n{st2l} {st2}\n{st3l} {st2}\n"
                    "{st4l} {st4}\n{st5l} {st5}\n{st6l} {st6}\n{st7l} {st7}\n"
                )
            }
        },
        'arm': {
            'horizontal': {

            },
            'vertical': {
            
            }
        }
    }
    FLAG_BITS = {'c': 0, 'p': 2, 'a': 4, 'z': 6, 's': 7, 't': 8, 'i': 9, 'd': 10, 'o': 11}
    FLAG_TEMPLATE = "[ {o} {d} {i} {t} {s} {z} {a} {p} {c} ]"
    XMM_INDENT = 7
    last_regs = None
    last_flags = None

    @classmethod
    def configure_subparser(cls, subparsers):
        sp = subparsers.add_parser('reg', help='register view')
        VoltronView.add_generic_arguments(sp)
        sp.set_defaults(func=RegisterView)
        g = sp.add_mutually_exclusive_group()
        g.add_argument('--horizontal', '-o',    dest="orientation", action='store_const',   const="horizontal", help='horizontal orientation')
        g.add_argument('--vertical', '-v',      dest="orientation", action='store_const',   const="vertical",   help='vertical orientation (default)')
        sp.add_argument('--general', '-g',      dest="sections",    action='append_const',  const="general",    help='show general registers')
        sp.add_argument('--no-general', '-G',   dest="sections",    action='append_const',  const="no_general", help='show general registers')
        sp.add_argument('--sse', '-s',          dest="sections",    action='append_const',  const="sse",        help='show sse registers')
        sp.add_argument('--no-sse', '-S',       dest="sections",    action='append_const',  const="no_sse",     help='show sse registers')
        sp.add_argument('--fpu', '-p',          dest="sections",    action='append_const',  const="fpu",        help='show fpu registers')
        sp.add_argument('--no-fpu', '-P',       dest="sections",    action='append_const',  const="no_fpu",     help='show fpu registers')

    def apply_cli_config(self):
        super(RegisterView, self).apply_cli_config()
        if self.args.orientation != None:
            self.config['orientation'] = self.args.orientation
        if self.args.sections != None:
            a = filter(lambda x: 'no_'+x not in self.args.sections and not x.startswith('no_'), self.config['sections'] + self.args.sections)
            self.config['sections'] = []
            for sec in a:
                if sec not in self.config['sections']:
                    self.config['sections'].append(sec)

    def render(self, msg=None):
        # Build template
        template = '\n'.join(map(lambda x: self.TEMPLATES['x64'][self.config['orientation']][x], self.config['sections']))

        # Process formatting settings
        data = defaultdict(lambda: 'n/a')
        data.update(msg['data'])
        formats = self.FORMAT_INFO['x64']
        formatted = {}
        for fmt in formats:
            # Apply defaults where they're missing
            fmt = dict(self.config['format_defaults'].items() + fmt.items())

            # Format the data for each register
            for reg in fmt['regs']:
                # Format the label
                label = fmt['label_format'].format(reg)
                if fmt['label_func'] != None:
                    formatted[reg+'l'] = eval(fmt['label_func'])(label)
                if fmt['label_colour_en']:
                    formatted[reg+'l'] =  colored(formatted[reg+'l'], fmt['label_colour'])

                # Format the value
                val = data[reg]
                if type(val) == str:
                    temp = fmt['value_format'].format(0)
                    if len(val) < len(temp):
                        val += (len(temp) - len(val))*' '
                    formatted[reg] = colored(val, fmt['value_colour'])
                else:
                    colour = fmt['value_colour']
                    if self.last_regs == None or self.last_regs != None and val != self.last_regs[reg]:
                        colour = fmt['value_colour_mod']
                    formatted[reg] = val
                    if fmt['value_format'] != None:
                        formatted[reg] = fmt['value_format'].format(formatted[reg])
                    if fmt['value_func'] != None:
                        if type(fmt['value_func']) == str:
                            formatted[reg] = eval(fmt['value_func'])(formatted[reg])
                        else:
                            formatted[reg] = fmt['value_func'](formatted[reg])
                    if fmt['value_colour_en']:
                        formatted[reg] = colored(formatted[reg], colour)

        # Prepare output
        log.debug('Formatted: ' + str(formatted))
        height, width = self.window_size()
        self.title = '[regs:{}]'.format('|'.join(self.config['sections']))
        if len(self.title) > width:
            self.title = '[regs]'
        self.body = template.format(**formatted)

        # Pad
        lines = self.body.split('\n')
        pad = self.body_height() - len(lines)
        if pad < 0:
            pad = 0
        self.body += pad*'\n'

        # Store the regs
        self.last_regs = data

        # Call parent's render method
        super(RegisterView, self).render()

    def format_flags(self, val):
        values = {}

        # Get formatting info for flags
        fmt = dict(self.config['format_defaults'].items() + filter(lambda x: 'rflags' in x['regs'], self.FORMAT_INFO['x64'])[0].items())

        # Handle each flag bit
        val = int(val, 10)
        formatted = {}
        for flag in self.FLAG_BITS.keys():
            values[flag] = (val & (1 << self.FLAG_BITS[flag]) > 0)
            log.debug("Flag {} value {} (for rflags 0x{})".format(flag, values[flag], val))
            formatted[flag] = str.upper(flag) if values[flag] else flag
            if self.last_flags != None and self.last_flags[flag] != values[flag]:
                colour = fmt['value_colour_mod']
            else:
                colour = fmt['value_colour']
            formatted[flag] = colored(formatted[flag], colour)

        # Store the flag values for comparison
        self.last_flags = values

        # Format with template
        return self.FLAG_TEMPLATE.format(**formatted)

    def format_xmm(self, val):
        if self.config['orientation'] == 'vertical':
            height, width = self.window_size()
            if width < len(SHORT_ADDR_FORMAT_128.format(0)) + self.XMM_INDENT:
                return val[:16] + '\n' + ' '*self.XMM_INDENT + val[16:]
            else:
                return val[:16] +  ':' + val[16:]
        else:
            return val

    def format_fpu(self, val):
        if self.config['orientation'] == 'vertical':
            return val
        else:
            return val

class DisasmView (TerminalView):
    VIEW_DEFAULT_CONFIG = {
        'type': 'disasm'
    }

    @classmethod
    def configure_subparser(cls, subparsers):
        sp = subparsers.add_parser('disasm', help='disassembly view')
        VoltronView.add_generic_arguments(sp)
        sp.set_defaults(func=DisasmView)

    def render(self, msg=None):
        height, width = self.window_size()

        # Get the disasm
        disasm = msg['data']
        disasm = '\n'.join(disasm.split('\n')[:self.body_height()])

        # Pygmentize output
        if have_pygments:
            try:
                lexer = pygments.lexers.get_lexer_by_name('gdb')
                disasm = pygments.highlight(disasm, lexer, pygments.formatters.Terminal256Formatter())
            except Exception as e:
                log.warning('Failed to highlight disasm: ' + str(e))

        # Build output
        self.title = '[code]'
        self.body = disasm.rstrip()

        # Call parent's render method
        super(DisasmView, self).render()
    

class StackView (TerminalView):
    VIEW_DEFAULT_CONFIG = {
        'type': 'stack'
    }

    @classmethod
    def configure_subparser(cls, subparsers):
        sp = subparsers.add_parser('stack', help='stack view')
        VoltronView.add_generic_arguments(sp)
        sp.add_argument('--bytes', '-b', action='store', type=int, help='bytes per line (default 16)', default=16)
        sp.set_defaults(func=StackView)

    def render(self, msg=None):
        height, width = self.window_size()

        # Get the stack data
        data = msg['data']
        stack_raw = data['data']
        sp = data['sp']
        stack_raw = stack_raw[:(self.body_height())*self.args.bytes]

        # Hexdump it
        lines = self.hexdump(stack_raw, offset=sp, length=self.args.bytes).split('\n')
        lines.reverse()
        stack = '\n'.join(lines)

        # Build output
        self.title = "[stack]"
        self.info = '[0x{0:0=4x}:'.format(len(stack_raw)) + ADDR_FORMAT_64.format(sp) + ']'
        self.body = stack.strip()

        # Call parent's render method
        super(StackView, self).render()


class BacktraceView (TerminalView):
    VIEW_DEFAULT_CONFIG = {
        'type': 'bt'
    }

    @classmethod
    def configure_subparser(cls, subparsers):
        sp = subparsers.add_parser('bt', help='backtrace view')
        VoltronView.add_generic_arguments(sp)
        sp.set_defaults(func=BacktraceView)

    def render(self, msg=None):
        height, width = self.window_size()

        # Get the back trace data
        data = msg['data']
        lines = data.split('\n')
        pad = self.body_height() - len(lines) + 1
        if pad < 0:
            pad = 0

        # Build output
        self.title = '[backtrace]'
        self.body = data.strip() + pad*'\n'

        # Call parent's render method
        super(BacktraceView, self).render()


class CommandView (TerminalView):
    VIEW_DEFAULT_CONFIG = {
        'type': 'cmd'
    }

    @classmethod
    def configure_subparser(cls, subparsers):
        sp = subparsers.add_parser('cmd', help='command view - specify a command to be run each time the debugger stops')
        VoltronView.add_generic_arguments(sp)
        sp.add_argument('command', action='store', help='command to run')
        sp.set_defaults(func=CommandView)

    def setup(self):
        self.config['cmd'] = self.args.command

    def render(self, msg=None):
        # Get the command output
        data = msg['data']
        lines = data.split('\n')
        pad = self.body_height() - len(lines) + 1
        if pad < 0:
            pad = 0

        # Build output
        self.title = '[cmd:' + self.config['cmd'] + ']'
        self.body = data.rstrip() + pad*'\n'

        # Call parent's render method
        super(CommandView, self).render()


def merge(d1, d2):
    for k1,v1 in d1.iteritems():
        if isinstance(v1, dict) and k1 in d2.keys() and isinstance(d2[k1], dict):
            merge(v1, d2[k1])
        else:
            d2[k1] = v1
    return d2
