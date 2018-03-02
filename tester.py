import sys
import os
import subprocess
import argparse
import time
from pdb import set_trace
# from constants import START_MESSAGE

# TEST_DIR = 'darshan-tests'
# SOLUTIONS_DIR = 'darshan-tests-solutions'

TEST_DIR = 'tests'
SOLUTIONS_DIR = 'tests-solutions'

def run_single_test(test_file, sol_file):
    print("Running test {}...".format(test_file))
    # Check test file ends with blank line.
    lines = open(test_file, 'r').readlines()
    if lines[-1] != "\n":
        error_msg = "Test does not end with a blank line!"
        return False, error_msg, 0
    cmd = "python master.py < {}".format(test_file)
    start_time = time.time()
    output = subprocess.check_output(cmd, shell=True)
    end_time = time.time()
    elapsed_sec = end_time - start_time
    output = output.decode("utf-8")
    # output = output[len(START_MESSAGE)+1:]
    if not os.path.exists(sol_file):
        success = (output == "")
        error_msg = None
        if not success:
            error_msg = "\nNon-empty output: \n{}".format(output)
        return success, error_msg, elapsed_sec
    solution = "".join(open(sol_file, 'r').readlines())
    success = (solution.rstrip() == output.rstrip())
    error_msg = None
    if not success:
        error_msg = "\nExpected output: \n{}\nActual output: \n{}" \
                .format(solution, output)
    return success, error_msg, elapsed_sec

def find_solution_file(test_file):
    return test_file[:test_file.find('.')] + '-solution.txt' # Sol.txt

def print_scoreboard(test_files, successes, error_msgs, times):
    success_count = 0
    total_count = 0
    failed_tests = list()
    print("------------------------------------------")
    for (test, success, error_msg, t) in zip(test_files, successes, error_msgs, times):
        print("######### TEST {} ##########".format(test))
        if success:
            print("SUCCESS! Info: Test took {} seconds".format(t))
            success_count += 1
        else:
            print("FAILURE! Info: Test took {} seconds".format(t))
            print("{}".format(error_msg))
            failed_tests.append(test)
        print()
        total_count += 1
    print("Failed tests: {}".format(failed_tests))
    print("Success percentage: {}".format(success_count / float(total_count)))
    print("------------------------------------------")

def main(tests):
    test_files, successes, error_msgs, times = list(), list(), list(), list()
    if tests == "all":
        for test_file in os.listdir(TEST_DIR):
            # Skip swap files.
            if test_file[0] == '.':
                continue
            sol_file_path = os.path.join(SOLUTIONS_DIR, find_solution_file(test_file))
            test_file_path = os.path.join(TEST_DIR, test_file)
            success, error_msg, secs = run_single_test(test_file_path, sol_file_path)
            test_files.append(test_file)
            successes.append(success)
            error_msgs.append(error_msg)
            times.append(secs)
    else:
        sol_file_path = os.path.join(SOLUTIONS_DIR, find_solution_file(tests))
        test_file_path = os.path.join(TEST_DIR, tests)
        success, error_msg, secs = run_single_test(test_file_path, sol_file_path)
        test_files.append(tests)
        successes.append(success)
        error_msgs.append(error_msg)
        times.append(secs)
    print_scoreboard(test_files, successes, error_msgs, times) 
        

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tests', type=str, default='all')
    args = parser.parse_args()
    main(args.tests)
