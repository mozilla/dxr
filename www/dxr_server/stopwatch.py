#!/usr/bin/env python2

import time

class StopWatch:
  def __init__ (self):
    self.timers = {}
    self.accumulated = {}

  def start (self, task_str):
    self.timers[task_str] = time.clock()

  def stop (self, task_str):
    if task_str in self.timers:
      if task_str in self.accumulated:
        self.accumulated[task_str] += time.clock() - self.timers[task_str]
      else:
        self.accumulated[task_str] = time.clock() - self.timers[task_str]

      del self.timers[task_str]

  def elapsed (self, task_str):
    el = 0

    if task_str in self.accumulated:
      el += self.accumulated[task_str]

    if task_str in self.timers:
      el += time.clock () - self.timers[task_str]

    return el
