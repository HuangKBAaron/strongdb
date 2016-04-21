# coding=utf-8

import os
import fcntl
import termios
import struct
import math


class Strongdb:
    modules = {}
    term_width = 0

    COLOR = {'black': '30m', 'red': '31m', 'green': '32m', 'yellow': '33m', 'blue': '34m', 'magenta': '35m',
             'cyan': '36m', 'white': '37m'}

    def __init__(self):
        self.set_custom_prompt()
        self.init_var()
        self.init_modules()
        self.init_handlers()

    def set_custom_prompt(self):
        def get_prompt(prompt):
            if self.is_debuggee_running():
                status = gdb.prompt.substitute_prompt("\[\e[0;32m\]-->\[\e[0m\]")
            else:
                status = gdb.prompt.substitute_prompt("\[\e[1;31m\]-->\[\e[0m\]")

            return status + " "

        gdb.prompt_hook = get_prompt

    def is_debuggee_running(self):
        return gdb.selected_inferior().pid != 0

    def init_var(self):
        Strongdb.term_width = Strongdb.get_terminal_width()

        Strongdb.run_cmd('set $sgdb_stack_width = 4')
        Strongdb.run_cmd('set pagination off')

    def init_handlers(self):
        # gdb.events.cont.connect(self.on_continue)
        gdb.events.stop.connect(self.on_stop)

    def init_modules(self):
        # self.modules.append({"name": "RegistersModule", "instance": RegistersModule()})
        self.modules['RegistersModule'] = RegistersModule()
        self.modules['StackModule'] = StackModule()
        self.modules['AssemblyModule'] = AssemblyModule()

    def on_continue(self, event):
        print "on continue"

    def on_stop(self, event):
        self.display(self.modules['RegistersModule'].get_contents(), True)
        self.display(self.modules['AssemblyModule'].get_contents())
        self.display(self.modules['StackModule'].get_contents())

    def display(self, info, clear_screen=False):
        if clear_screen:
            self.clear_screen()

        gdb.write(info)

    @staticmethod
    def is_arm_mode():
        value = int(Strongdb.run_cmd('i r cpsr').split(None)[1], 16)
        return not (value & 0x20)

    @staticmethod
    def clear_screen():
        gdb.write("\x1b[H\x1b[J")

    @staticmethod
    def get_terminal_width(fd=1):
        hw = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
        return hw[1]

    @staticmethod
    def run_cmd(gdb_cmd):
        return gdb.execute(gdb_cmd, to_string=True)

    @staticmethod
    def colorize(str, color="black"):
        return "\x1b[" + Strongdb.COLOR[color] + str + "\x1b[0m"

    @staticmethod
    def get_display_padding(max_len):
        groups_per_line = (Strongdb.term_width) / max_len
        padding = int(math.floor(float(Strongdb.term_width % max_len) / float(groups_per_line)))

        return (groups_per_line, padding)


class RegistersModule():
    old_regs = {}
    reg_names = []

    def get_contents(self, all_regs=False):
        str = ""

        self.get_regs_info()

        max_name_len = max(len(name) for name in self.reg_names)
        max_len = 25
        # regs_per_line = (Strongdb.term_width) / max_len
        # spaces = int(math.floor(float(Strongdb.term_width % max_len) / float(regs_per_line)))
        regs_per_line, padding = Strongdb.get_display_padding(max_len)

        str += Strongdb.colorize('┌─ Register ' + '─' * (Strongdb.term_width - 13) + '┐\n', 'cyan')
        i = 1;
        for reg_name in self.reg_names:
            if self.old_regs[reg_name]['is_changed'] == True:
                str += Strongdb.colorize(' ' * 5 + reg_name.rjust(4), 'red') + '-' + Strongdb.colorize(
                        self.old_regs[reg_name]['value'], 'white') + ' ' * 5
            else:
                str += Strongdb.colorize(' ' * 5 + reg_name.rjust(4), 'red') + '-' + Strongdb.colorize(
                        self.old_regs[reg_name]['value'], 'black') + ' ' * 5

            if i == regs_per_line:
                i = 0
                str += '\n'

            i += 1

        str += Strongdb.colorize('\n└' + '─' * (Strongdb.term_width - 2) + '┘', 'cyan')
        return str


    def get_regs_info(self):
        regs = Strongdb.run_cmd("i r").strip().split('\n')
        self.reg_names = []


        run_start = len(self.old_regs) == 0
        for reg_info in regs:
            reg = reg_info.split(None)

            # if all_regs == False and "cs,ss,ds,es,fs,gs".find(reg[0]) != -1:
            #     continue

            reg_name = reg[0]
            self.reg_names.append(reg_name)
            if reg[1][0: 2] == '0x':
                reg_value_hex = '0x' + reg[1][2:].rjust(8, '0')
            else:
                reg_value_hex = reg[1].ljust(18)

            if run_start:
                # self.old_regs.append({reg_name: "{'value' : " + reg_value_hex + ", 'is_changed' : False}"})
                self.old_regs[reg_name] = {'value': reg_value_hex, 'is_changed': False}
            else:
                if reg_value_hex != self.old_regs[reg_name]['value']:
                    self.old_regs[reg_name] = {'value': reg_value_hex, 'is_changed': True}
                else:
                    self.old_regs[reg_name] = {'value': reg_value_hex, 'is_changed': False}



class BacktraceModule():
    def get_contents(self):
        return ""


class StackModule():
    stack_info = []

    def get_contents(self):
        str = ""

        self.stack_info = []
        str += Strongdb.colorize('┌─ Stack ' + '─' * (Strongdb.term_width - 10) + '┐\n', 'cyan')

        self.get_stack_info()

        for line in self.stack_info:
            for idx in range(len(line)):
                if idx == 0:
                    str += Strongdb.colorize('\t' + line[idx] + '\t\t', 'red')
                else:
                    str += Strongdb.colorize(line[idx] + '   ', 'black')

                if idx == len(line) - 1:
                    str += '\n'

        str += Strongdb.colorize('└' + '─' * (Strongdb.term_width - 2) + '┘', 'cyan')
        return str

    def get_stack_info(self):
        stack_info = Strongdb.run_cmd("x/48bx $sp").strip().split('\n')
        for line in stack_info:
            line_list = line.split(None)
            line_list.append(Strongdb.colorize('│', 'cyan'))
            for idx in range(1, 9):
                if int(line_list[idx], 16) > 0x20 and int(line_list[idx], 16) < 0x7f:
                    line_list.append(chr(int(line_list[idx], 16)))
                else:
                    line_list.append('·')
            self.stack_info.append(line_list)


class AssemblyModule():
    def get_contents(self):
        str = ""
        str += Strongdb.colorize('┌─ Assembly ' + '─' * (Strongdb.term_width - 13) + '┐\n\n', 'cyan')

        if Strongdb.is_arm_mode():
            length_per_ins = 4
        else:
            length_per_ins = 2

        frame = gdb.selected_frame()
        instructions = frame.architecture().disassemble(frame.pc() - 4 * length_per_ins, count=10)


        for ins in instructions:
            if frame.pc() == ins['addr']:
                str += Strongdb.colorize('-->\t' + hex(ins['addr'])[:-1] + ':\t', 'red')
                str += Strongdb.colorize(ins['asm'], 'green') + '\n'
            else:
                str += Strongdb.colorize('\t' + hex(ins['addr'])[:-1] + ':\t', 'red')
                str += Strongdb.colorize(ins['asm'], 'white') + '\n'


        str += Strongdb.colorize('\n└' + '─' * (Strongdb.term_width - 2) + '┘', 'cyan')
        Strongdb.is_arm_mode()
        return str


class HelloWorld(gdb.Command):
    def __init__(self):
        super(HelloWorld, self).__init__("hello-world", gdb.COMMAND_USER)

    def invoke(self, args, from_tty):
        argv = gdb.string_to_argv(args)
        if len(argv) != 0:
            raise gdb.GdbError("hello-world takes no arguments")
        print "hello world!"


HelloWorld()
p = Strongdb()
