import threading
import Queue
import gobject
gobject.threads_init()

class GObjectWorker():
	def __init__(self):
		self.thread = threading.Thread(target=self._run)
		self.thread.daemon = True
		self.queue = Queue.Queue()
		self.thread.start()
		
	def _run(self):
		while True:
			command, args, callback, errorback = self.queue.get()
			try:
				result = command(*args)
				gobject.idle_add(callback, result)
			except Exception, e:
				gobject.idle_add(errorback, e)
				
	def send(self, command, args, callback, errorback=None):
		if errorback is None: errorback = self._default_errorback
		self.queue.put((command, args, callback, errorback))
		
	def _default_errorback(self, error):
		print "Unhandled exception in worker thread:", error
		
if __name__ == '__main__':
	worker = GObjectWorker()
	import time, gtk
	
	def test_cmd(a, b):
		print "running..."
		time.sleep(5)
		print "done"
		return a*b
		
	def test_cb(result):
		print "got result", result
		
	print "sending"
	worker.send(test_cmd, (3,4), test_cb)
	worker.send(test_cmd, ((), ()), test_cb) #trigger exception in worker to test error handling
	
	gtk.main()
		
				
