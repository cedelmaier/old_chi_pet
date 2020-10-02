#!/usr/bin/env python
import sys
import os
import yaml
import argparse
import re
import fnmatch

from pathlib import Path
from subprocess import Popen, PIPE

# Creates multithreaded processor jobs.
#!/bin/bash
# SBATCH --job-name={0}
# SBATCH -t {1}
# SBATCH -N {2}
# SBATCH --ntasks-per-node {3}
# SBATCH --cpus-per-task {4}
# SBATCH -o {5}
# SBATCH -e {6}
# SBATCH --constraint={7}
# SBATCH --partition={8}

# cd $SLURM_SUBMIT_DIR


def create_multiprocessor_job(seedpaths, statelist, job_name="ChiRun",
                              walltime="1:00", nnodes="1", ntasks="20",
                              nprocs="1", constraint="skylake", queue="ccb",
                              args_file="args.yaml", name="job.slurm",
                              env_sh='SetEnv.sh'):
    print("creating jobs for:")
    for i, sd_path in enumerate(seedpaths):
        print("sim: {0} with states: {1}".format(
            sd_path, ", ".join(statelist[i])))
    print("")

    # Customize your options here
    job_name = 'ChiRunBatch'
    seedlaunchpath = Path(__file__).resolve().parent / 'ChiRun.py'
    # seedlaunchpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    # 'ChiRun.py')
    log = '/dev/null'
    errlog = '/dev/null'
    if walltime.count(':') == 3:
        walltime = walltime.replace(':', '-', 1)

    # Slurm submission code
    # Open a pipe to the sbatch command.
    # output, input = Popen('sbatch')
    # p = Popen('sbatch', stdin=PIPE, stdout=PIPE)
    # output, input = (p.stdout, p.stdin)

    job_string = """# DisBatch task file made with chi-Pet
#DISBATCH PREFIX  cd {0} ; source {1} ; \n
""".format(Path.cwd(), env_sh)

    for i, sd_path in enumerate(seedpaths):
        # sd_path = os.path.abspath(sd_path)
        sd_path = Path(sd_path).resolve()
        command = "{0} -d {1} -a {2} -s {3}".format(
            seedlaunchpath, sd_path, args_file, " ".join(statelist[i]))
        # log = os.path.join(sd_path, 'sim.log')
        log = sd_path / 'sim.log'
        # errlog = os.path.join(sd_path, 'sim.err')
        errlog = sd_path / 'sim.err'
        job_string += "{0} 1> {1} 2> {2} \n".format(command, log, errlog)
    # job_string = job_string + "wait\n"

    with open(name, 'w') as input:
        # input.write(job_string.encode('utf-8'))
        input.write(job_string)

    # Send job_string to qsub
    # input.close()

    # Print your job and the response to the screen
    # print(job_string)
    # print(output.read())


def get_state(path):
    state = []
    # Find all sim.* (excluding sim.err and sim.log)
    file_pat = re.compile(r'sim\.(?!err)(?!log).+')
    for f in os.listdir(path):
        if file_pat.match(f):
            # WARNING states may not have a '.' in the name.
            state.append(f.split('.')[-1])
            # TODO In future use look ahead function in re.match to
            # to find correct state with list comprehension
    return state


def is_running(path):
    return os.path.isfile(os.path.join(path, '.running'))


def is_error(path):
    return os.path.isfile(os.path.join(path, '.error'))


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def ChiLaunch(simdirs, opts=''):
    # List of all the seeds that will be run
    seeddirs = []

    if opts and opts.args_file:
        args_file = opts.args_file
    else:
        args_file = "args.yaml"

    for simd in simdirs:
        print("Searching for path {0}".format(simd))

        if fnmatch.fnmatch(simd, '*.txt'):
            print("Ignoring text file {}".format(simd))
            continue
        if os.path.exists(simd):
            print("path exists, checking for seeds...")
            seeddirs = seeddirs + [os.path.join(simd, f) for f in os.listdir(simd)
                                   if os.path.isdir(os.path.join(simd, f))
                                   and not f.startswith('.')]
            if not seeddirs:
                print("no seeds found in sim directory")
                return 1
        else:
            print("sim does not exist")
            return 1

    # Determines the programs that will be run on seed directories
    runstates = input(
        "List space separated states you wish to run (leave blank for all): ").split(' ')
    if runstates[0] == '':
        runstates = 'all'

    seeds = []  # Seed directories to be run
    states = []  # States of seed directories

    # Go through all seed directories and see if they are capable of running
    # ei. No .error file and no .running file
    for sdd in seeddirs:
        if not is_running(sdd) and not is_error(sdd):
            state = get_state(sdd)
            # print state
            if runstates != 'all':
                state = list(set(state).intersection(set(runstates)))
            if state:
                seeds.append(sdd)
                states.append(state)
    print("Jobs found: {0}".format(len(seeds)))

    n_jobs = input(
        'Input number of jobs to run, (default {0}): '.format(
            len(seeds))).strip()
    if n_jobs == '':
        n_jobs = len(seeds)
    else:
        n_jobs = int(n_jobs)

    scheduler = input('Input scheduler (default slurm): ').strip()
    if scheduler == '' or scheduler == 'slurm':
        scheduler, queue, nprocs = ("slurm", "ccb", "1")
    else:
        print("Chi-pet is not programmed for scheduler '{}'.".format(scheduler))
        sys.exit(1)

    constraint = input('Input node type (default skylake)')
    if constraint == '':
        constraint = 'skylake'

    queue_switch = input(
        'Input job queue (default {}): '.format(queue)).strip()
    if queue_switch != '':
        queue = queue_switch

    walltime = input(
        'Input walltime (dd:hh:mm:ss), (default 23:59:00): ').strip()
    if walltime == '':
        walltime = "23:59:00"

    nodes = input('Input number of nodes (default 1): ').strip()
    if nodes == '':
        nodes = "1"

    ntasks = input('Input number of tasks per node (default 20): ').strip()
    if ntasks == '':
        ntasks = "20"

    nprocs_switch = input(
        'Input number of processors per task (default {}): '.format(nprocs)).strip()
    if nprocs_switch != '':
        nprocs = nprocs_switch

    if not query_yes_no("Generating job for states ({0}) with walltime ({1}) on ({2}) nodes in queue ({3}) with scheduler ({4}).".format(
            " ".join(runstates), walltime, constraint, queue, scheduler)):
        return 1

    # processors = "nodes={0}:ppn={1}".format(nodes,ppn)
    # TODO disBatch makes this unecessary I think?
    for i_block in range(0, int(n_jobs / int(ntasks)) + 1):
        # Find the index range of the seeds that you are running
        starti = i_block * int(ntasks)
        endi = starti + int(ntasks)
        # If end index is greater the number of seeds make end the last seed
        # run
        print(seeds)
        if endi > len(seeds):
            endi = len(seeds)
        if endi > starti:
            create_multiprocessor_job(seeds[starti:endi], states[starti:endi],
                                      walltime=walltime, nnodes=nodes,
                                      ntasks=ntasks, nprocs=nprocs,
                                      constraint=constraint, queue=queue,
                                      args_file=args_file,
                                      name="job{}-{}.slurm".format(starti, endi))
        # Torque scheduler has a 10 second update time
        # make sure you wait before adding another
        import time
        if scheduler == "torque":
            time.sleep(10)
        else:
            time.sleep(.1)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Arguments are the simulation directories to be run
        ChiLaunch(simdirs=sys.argv[1:], opts='')
    else:
        print("must supply directory argument")
