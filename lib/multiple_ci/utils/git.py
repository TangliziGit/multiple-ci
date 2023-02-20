import logging
import os.path
import subprocess
import time

from multiple_ci.config import config


class RepoSpinlock:
    def __init__(self, repo_path):
        self.lockfile_path = os.path.join(repo_path, '.git', 'txn.lock')

    def __enter__(self):
        while True:
            if self.__lock_repo():
                return
            time.sleep(config.GIT_TXN_SPINLOCK_INTERVAL_SEC)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__unlock_repo()

    def __lock_repo(self):
        now = time.time_ns()
        if not os.path.exists(self.lockfile_path):
            try:
                # create new txn atomically
                # ref: https://linux.die.net/man/2/open
                fd = os.open(self.lockfile_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                os.write(fd, str(now).encode())
                os.close(fd)
                return True
            except FileExistsError:
                return False

        with open(self.lockfile_path, 'r') as lockfile:
            timestamp = int(lockfile.readline())
            if now - timestamp < config.GIT_TXN_LOCK_TIMEOUT_NS:
                return False

        # if lockfile timeout, then unlock it and try to lock it
        self.__unlock_repo()
        return self.__lock_repo()

    def __unlock_repo(self):
        os.remove(self.lockfile_path)


class RepoTransaction:
    def __init__(self, repo_path, commit_id):
        self.repo_path = repo_path
        self.commit_id = commit_id
        self.prev_commit_id = None
        self.lock = RepoSpinlock(repo_path)

    def __enter__(self):
        self.lock.__enter__()
        cmd = f'git -C {self.repo_path} --no-pager log --pretty=format:"%H" -n 1'
        self.prev_commit_id = subprocess.check_output(cmd.split(" ")).decode('utf-8')

        cmd = f'git -C {self.repo_path} reset --hard {self.commit_id}'
        subprocess.run(cmd.split(" "))

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.__exit__(exc_type, exc_val, exc_tb)
        cmd = f'git -C {self.repo_path} reset --hard {self.prev_commit_id}'
        subprocess.run(cmd.split(" "))

def run(command, repo_path=None, commit_id=None):
    """
    Run git CLI in a transactional way, i.e. atomize git commands
     to achieve serialization of repository access.

    :param command: git CLI command without `git` prefix, for example: `pull --rebase`
    :param repo_path:
    :param commit_id:
    :return output of the git command
    """
    # check arguments validation
    if repo_path is None and commit_id is not None:
        error = f"invalid arguments in git.run function: command={command}, " \
                f"repo_path={repo_path}, commit_id={commit_id}"
        logging.error(error)
        raise RuntimeError(error)

    if repo_path is None:
        # ASERT: commit_id is None
        return subprocess.check_output(f'git {command}'.split(" ")).decode('utf-8')

    with RepoSpinlock(repo_path):
        if commit_id is None:
            # It means you want to access the repo with the latest commit
            return subprocess.check_output(f'git -C {repo_path} --no-pager {command}'.split(" ")).decode('utf-8')

        cmd = f'git -C {repo_path} --no-pager log --pretty=format:"%H" -n 1'
        prev_commit_id = subprocess.check_output(cmd.split(" ")).decode('utf-8')

        cmd = f'git -C {repo_path} reset --hard {commit_id}'
        subprocess.run(cmd.split(" "))

        cmd = f'git -C {repo_path} --no-pager {command}'
        output = subprocess.check_output(cmd.split(" ")).decode('utf-8')

        cmd = f'git -C {repo_path} reset --hard {prev_commit_id}'
        subprocess.run(cmd.split(" "))

    return output