from threading import Thread

STATUS_FAILED = -1;
STATUS_STOPPED = 0;
STATUS_RUNNING = 1;
STATUS_PAUSED = 2;
STATUS_COMPLETE = 3;


'''
    SubTaskWrapper - class used to store additional information
     about the relationship between a container and a subtask.

     percentage - the percentage of work the task accounts for.
'''
class SubTaskWrapper():
    def __init__(self, task, percentage):
        self.task = task
        self.percentage = percentage

'''
    WorkUnit - class used to wrap task work in a thread.  New WorkUnits
    can be constructed every time a task is run.  This gives the task the ability
    to be run multiple times, which a standard thread cannot do.
'''
class WorkUnit(Thread):
    def __init__(self, parent, args):
        Thread.__init__(self)
        self.parent = parent
        self.args = args

    def run(self):
        #self.parent.running = 1
        #self.parent.finished = 0
        self.parent.status = STATUS_RUNNING
        result = self.doTask(self.args)
        self.parent.status = STATUS_COMPLETE
        #self.parent.running = 0
        #self.parent.finished = 1
        return result

    def doTask(self,args):
        self.parent.workFunction(args)

'''
    Task - class that wraps a set of functions as a runnable unit of work.  Once
    wrapped the task allows functions to be managed and tracked in a uniform way.
'''
class Task():
    def __init__(self, msg, workFunction, progressFunction=None, progressMessageFunction=None):
        self.msg = msg
        self.workFunction = workFunction
        self.progressFunction = progressFunction
        self.progressMessageFunction = progressMessageFunction
        self.workunit = None
        #self.running = 0
        #self.finished = 0
        self.status = STATUS_STOPPED
        self.id = 1

    def reset(self):
        self.status = STATUS_STOPPED

    def start(self, args=None):
        # only start if not already running
        if self.status == STATUS_RUNNING:
            return

        # create a new workunit if needed
        if self.workunit == None or self.status == STATUS_COMPLETE:
            self.workunit = WorkUnit(self, args)

        self.workunit.start()

    def doTask(self, args):
        self.status = STATUS_RUNNING
        result = self.workFunction(args)
        self.status = STATUS_COMPLETE
        return result

    def progress(self):
        if self.progressFunction == None:
            return 0
        else:
            return self.progressFunction()

    def progressMessage(self):
        if self.progressMessageFunction == None:
            return None
        else:
            return self.progressMessageFunction()
        
    def getStatus(self):
        return self.status;

'''
    TaskContainer - an extension of Task that contains other tasks

    TaskContainer does no work itself.  Its purpose is to allow a bigger job
    to be broken into discrete functions.  IE.  downloading and processing.
'''
class TaskContainer(Task):

    def __init__(self, msg, sequential=True):
        Task.__init__(self, msg, self.iterateTasks, None)
        self.subtasks = []
        self.sequential = sequential

    def addTask(self, task, percentage=None):
        subtask = SubTaskWrapper(task, percentage)
        self.subtasks.append(subtask)
        task.id = '%s-%d' % (self.id,len(self.subtasks))

    def reset(self):
        for subtask in self.subtasks:
            subtask.task.reset()

    # Starts the task running all subtasks
    def iterateTasks(self, args=None):
        self.reset()

        result = None
        for subtask in self.subtasks:
            if self.sequential:
                #sequential task, run the task work directly (default)
                result = subtask.task.doTask(result)
            else:
                #parallel task, run the subtask in its own thread
                result = subtask.task.doTask(result)

        return result


    '''
        calculatePercentage - determines the percentage of work that each
        child task accounts for.

        TODO: take into account tasks that have had weighting manually set. 
    '''
    def calculatePercentage(self):
        return float(1)/len(self.subtasks);


    '''
        progress - returns the progress as a number 0-100.  

        A container task's progress is a derivitive of its children.
        the progress of the child counts for a certain percentage of the 
        progress of the parent.  This weighting can be set manually or
        divided evenly by calculatePercentage()
    '''
    def progress(self):
        progress = 0
        for subtask in self.subtasks:
            if subtask.percentage == None:
                percentage = self.calculatePercentage()
            else:
                percentage = subtask.percentage

            # if task is done it complete 100% of its work 
            if subtask.task.status == STATUS_COMPLETE:
                progress += 100*percentage
            # task is only partially complete
            else:
                progress += subtask.task.progress()*percentage

        return progress


    '''
        getStatus - returns status of this task.  A container task's status is 
        a derivitive of its children.

        failed - if any children failed, then the task failed
        running - if any children are running then the task is running
        paused - paused if no other children are running
        complete - complete if all children are complete
        stopped - default response if no other conditions are met
    '''
    def getStatus(self):
        has_paused = False;
        has_unfinished = False;

        for subtask in self.subtasks:
            subtaskStatus = subtask.task.getStatus()
            if subtaskStatus == STATUS_RUNNING:
                # we can return right here because if any child is running the 
                # container is considered to be running
                return STATUS_RUNNING

            elif subtaskStatus == STATUS_FAILED:
                # we can return right here because if any child failed then the
                # container is considered to be failed.  All other running tasks
                # should be stopped on failure.
                return STATUS_FAILED

            elif subtaskStatus == STATUS_PAUSED:
                has_paused = True

            elif subtaskStatus <> STATUS_COMPLETE:
                has_unfinished = True

        # Task is not running or failed.  If any are paused
        # then the container is paused
        if has_paused:
            return STATUS_PAUSED

        # task is not running, failed, or paused.  if all children are complete then it is complete
        if not has_unfinished:
            return STATUS_COMPLETE

        # only status left it could be is STOPPED
        return STATUS_STOPPED


'''
   TaskManager - Class that tracks and controls tasks
'''
class TaskManager():

    def __init__(self, task):
        self.task = task

    def processTask(self, task, tasklist=None, parent=False):
        # initial call wont have an area yet
        if tasklist==None:
            tasklist = []

        #turn the task into a tuple
        processedTask = [task.id, parent, task.msg]

        #add that task to the list
        tasklist.append(processedTask)

        #add all children if the task is a container
        if isinstance(task,TaskContainer):
            for subtask in task.subtasks:
                self.processTask(subtask.task, tasklist, task.id)

        return tasklist

    def processTaskProgress(self, task, tasklist=None):
        # initial call wont have an area yet
        if tasklist==None:
            tasklist = []

        #turn the task into a tuple
        processedTask = {'id':task.id, 'status':task.getStatus(), 'progress':task.progress(), 'msg':task.progressMessage()}

        #add that task to the list
        tasklist.append(processedTask)

        #add all children if the task is a container
        if isinstance(task,TaskContainer):
            for subtask in task.subtasks:
                self.processTaskProgress(subtask.task, tasklist)

        return tasklist

    def listTasks(self):
        return self.processTask(self.task)

    def progress(self):
        progress = self.processTaskProgress(self.task)

        message = {
                    'status':progress
                  }

        return message

    def start(self):
        self.task.start()
        return '1'

    def stop(self):
        pass
