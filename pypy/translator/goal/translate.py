#! /usr/bin/env python
"""
Command-line options for translate:

    See below
"""
import sys, os, new

import autopath 

from pypy.config.config import to_optparse, OptionDescription, BoolOption, \
                               ArbitraryOption, StrOption, IntOption, Config, \
                               ChoiceOption, OptHelpFormatter
from pypy.config.translationoption import get_combined_translation_config


GOALS= [
        ("annotate", "do type inference", "-a --annotate", ""),
        ("rtype", "do rtyping", "-t --rtype", ""),
        ("prehannotatebackendopt", "backend optimize before hint-annotating",
         "--prehannotatebackendopt", ""),
        ("hintannotate", "hint-annotate", "--hintannotate", ""),
        ("timeshift", "timeshift (jit generation)", "--timeshift", ""),
        ("backendopt", "do backend optimizations", "--backendopt", ""),
        ("source", "create source", "-s --source", ""),
        ("compile", "compile", "-c --compile", " (default goal)"),
        ("?jit", "generate JIT", "--jit", ""),
        ("run", "run the resulting binary", "--run", ""),
        ("llinterpret", "interpret the rtyped flow graphs", "--llinterpret", ""),
       ]
def goal_options():
    result = []
    for name, doc, cmdline, extra in GOALS:
        optional = False
        if name.startswith('?'):
            optional = True
            name = name[1:]
        yesdoc = doc[0].upper()+doc[1:]+extra
        result.append(BoolOption(name, yesdoc, default=False, cmdline=cmdline,
                                 negation=False))
        if not optional:
            result.append(BoolOption("no_%s" % name, "Don't "+doc, default=False,
                                     cmdline="--no-"+name, negation=False))
    return result

translate_optiondescr = OptionDescription("translate", "XXX", [
    IntOption("graphserve", """Serve analysis graphs on port number
(see pypy/translator/tool/pygame/graphclient.py)""",
              cmdline="--graphserve"),
    StrOption("targetspec", "XXX", default='targetpypystandalone',
              cmdline=None),
    BoolOption("profile",
               "cProfile (to debug the speed of the translation process)",
               default=False,
               cmdline="--profile"),
    BoolOption("batch", "Don't run interactive helpers", default=False,
               cmdline="--batch", negation=False),
    IntOption("huge", "Threshold in the number of functions after which "
                      "a local call graph and not a full one is displayed",
              default=100, cmdline="--huge"),
    BoolOption("text", "Don't start the pygame viewer", default=False,
               cmdline="--text", negation=False),
    BoolOption("help", "show this help message and exit", default=False,
               cmdline="-h --help", negation=False),
    ArbitraryOption("goals", "XXX",
                    defaultfactory=list),
    # xxx default goals ['annotate', 'rtype', 'backendopt', 'source', 'compile']
    ArbitraryOption("skipped_goals", "XXX",
                    defaultfactory=lambda: ['run']),
    OptionDescription("goal_options",
                      "Goals that should be reached during translation", 
                      goal_options()),        
])

    
OVERRIDES = {
    'translation.debug': False,
    'translation.insist': False,

    'translation.gc': 'boehm',
    'translation.backend': 'c',
    'translation.stackless': False,
    'translation.backendopt.raisingop2direct_call' : False,
    'translation.backendopt.merge_if_blocks': True,

    'translation.cc': None,
    'translation.profopt': None,
    'translation.output': None,
}

import py
# we want 2.4 expand_default functionality
optparse = py.compat.optparse
from pypy.tool.ansi_print import ansi_log
log = py.log.Producer("translation")
py.log.setconsumer("translation", ansi_log)

def load_target(targetspec):
    log.info("Translating target as defined by %s" % targetspec)
    if not targetspec.endswith('.py'):
        targetspec += '.py'
    thismod = sys.modules[__name__]
    sys.modules['translate'] = thismod
    specname = os.path.splitext(os.path.basename(targetspec))[0]
    sys.path.insert(0, os.path.dirname(targetspec))
    mod = __import__(specname)
    return mod.__dict__

def parse_options_and_load_target():
    opt_parser = optparse.OptionParser(usage="%prog [options] [target] [target-specific-options]",
                                       prog="translate",
                                       formatter=OptHelpFormatter(),
                                       add_help_option=False)

    opt_parser.disable_interspersed_args()

    config = get_combined_translation_config(
                overrides=OVERRIDES, translating=True)
    to_optparse(config, parser=opt_parser, useoptions=['translation.*'])
    translateconfig = Config(translate_optiondescr)
    to_optparse(translateconfig, parser=opt_parser)

    options, args = opt_parser.parse_args()

    # set goals and skipped_goals
    reset = False
    for name, _, _, _ in GOALS:
        if name.startswith('?'):
            continue
        if getattr(translateconfig.goal_options, name):
            if name not in translateconfig.goals:
                translateconfig.goals.append(name)
        if getattr(translateconfig.goal_options, 'no_'+name):
            if name not in translateconfig.skipped_goals:
                if not reset:
                    translateconfig.skipped_goals[:] = []
                    reset = True
                translateconfig.skipped_goals.append(name)
        
    if args:
        arg = args[0]
        args = args[1:]
        if os.path.isfile(arg+'.py'):
            assert not os.path.isfile(arg), (
                "ambiguous file naming, please rename %s" % arg)
            translateconfig.targetspec = arg
        elif os.path.isfile(arg) and arg.endswith('.py'):
            translateconfig.targetspec = arg[:-3]
        else:
            log.ERROR("Could not find target %r" % (arg, ))
            sys.exit(1)

    targetspec = translateconfig.targetspec
    targetspec_dic = load_target(targetspec)

    if args and not targetspec_dic.get('take_options', False):
        log.WARNING("target specific arguments supplied but will be ignored: %s" % ' '.join(args))

    # give the target the possibility to get its own configuration options
    # into the config
    if 'get_additional_config_options' in targetspec_dic:
        optiondescr = targetspec_dic['get_additional_config_options']()
        config = get_combined_translation_config(
                optiondescr,
                existing_config=config,
                translating=True)

    # let the target modify or prepare itself
    # based on the config
    if 'handle_config' in targetspec_dic:
        targetspec_dic['handle_config'](config)

    if 'handle_translate_config' in targetspec_dic:
        targetspec_dic['handle_translate_config'](translateconfig)

    if translateconfig.help:
        opt_parser.print_help()
        if 'print_help' in targetspec_dic:
            print "\n\nTarget specific help:\n\n"
            targetspec_dic['print_help'](config)
        print "\n\nFor detailed descriptions of the command line options see"
        print "http://codespeak.net/pypy/dist/pypy/doc/config/commandline.html"
        sys.exit(0)
    
    return targetspec_dic, translateconfig, config, args

def log_options(options, header="options in effect"):
    # list options (xxx filter, filter for target)
    log('%s:' % header)
    optnames = options.__dict__.keys()
    optnames.sort()
    for name in optnames:
        optvalue = getattr(options, name)
        log('%25s: %s' %(name, optvalue))
   
def log_config(config, header="config used"):
    log('%s:' % header)
    log(str(config))

def main():
    targetspec_dic, translateconfig, config, args = parse_options_and_load_target()
    from pypy.translator import translator
    from pypy.translator import driver
    from pypy.translator.tool.pdbplus import PdbPlusShow
    if translateconfig.profile:
        from cProfile import Profile
        prof = Profile()
        prof.enable()
    else:
        prof = None

    t = translator.TranslationContext(config=config)

    class ServerSetup:
        async_server = None
        
        def __call__(self, port=None, async_only=False):
            try:
                t1 = drv.hint_translator
            except (NameError, AttributeError):
                t1 = t
            if self.async_server is not None:
                return self.async_server
            elif port is not None:
                from pypy.translator.tool.graphserver import run_async_server
                serv_start, serv_show, serv_stop = self.async_server = run_async_server(t1, translateconfig, port)
                return serv_start, serv_show, serv_stop
            elif not async_only:
                from pypy.translator.tool.graphserver import run_server_for_inprocess_client
                return run_server_for_inprocess_client(t1, translateconfig)

    server_setup = ServerSetup()
    server_setup(translateconfig.graphserve, async_only=True)

    pdb_plus_show = PdbPlusShow(t) # need a translator to support extended commands

    def debug(got_error):
        if prof:
            prof.disable()
            statfilename = 'prof.dump'
            log.info('Dumping profiler stats to: %s' % statfilename)
            prof.dump_stats(statfilename)
        tb = None
        if got_error:
            import traceback
            errmsg = ["Error:\n"]
            exc, val, tb = sys.exc_info()
            errmsg.extend([" %s" % line for line in traceback.format_exception(exc, val, tb)])
            block = getattr(val, '__annotator_block', None)
            if block:
                class FileLike:
                    def write(self, s):
                        errmsg.append(" %s" % s)
                errmsg.append("Processing block:\n")
                t.about(block, FileLike())
            log.ERROR(''.join(errmsg))
        else:
            log.event('Done.')

        if translateconfig.batch:
            log.event("batch mode, not calling interactive helpers")
            return
        
        log.event("start debugger...")

        pdb_plus_show.start(tb, server_setup, graphic=not translateconfig.text)

    try:
        drv = driver.TranslationDriver.from_targetspec(targetspec_dic, config, args,
                                                       empty_translator=t,
                                                       disable=translateconfig.skipped_goals,
                                                       default_goal='compile')
        log_config(translateconfig, "translate.py configuration")
        if translateconfig.goal_options.jit:
            if 'portal' not in targetspec_dic:
               raise Exception('target has no portal defined.') 
            drv.set_extra_goals(['timeshift'])
        log_config(config.translation, "translation configuration")
        pdb_plus_show.expose({'drv': drv, 'prof': prof})

        if config.translation.output:
            drv.exe_name = config.translation.output
        elif drv.exe_name is None and '__name__' in targetspec_dic:
            drv.exe_name = targetspec_dic['__name__'] + '-%(backend)s'

        goals = translateconfig.goals
        drv.proceed(goals)
        
    except SystemExit:
        raise
    except:
        debug(True)
        raise SystemExit(1)
    else:
        debug(False)


if __name__ == '__main__':
    main()
