import logging
import uuid
import sys

from io import StringIO
from impacket.dcerpc.v5.dtypes import NULL

class executeVBS_Toolkit():
    def __init__(self, iWbemLevel1Login):
        self.iWbemLevel1Login = iWbemLevel1Login

    @staticmethod
    def checkError(banner, resp):
        call_status = resp.GetCallStatus(0) & 0xffffffff  # interpret as unsigned
        if call_status != 0:
            from impacket.dcerpc.v5.dcom.wmi import WBEMSTATUS
            try:
                error_name = WBEMSTATUS.enumItems(call_status).name
            except ValueError:
                error_name = 'Unknown'
            logging.error('%s - ERROR: %s (0x%08x)' % (banner, error_name, call_status))
        else:
            logging.info('%s - OK' % banner)

    def ExecuteVBS(self, vbs_file=None, vbs_content=None, filer_Query=None, timer=1000, returnTag=False):
        if vbs_content == None and vbs_file != None:
            with open(vbs_file,'r') as f: vbs_content = f.read()
        iWbemServices = self.iWbemLevel1Login.NTLMLogin('//./root/subscription', NULL, NULL)
        self.iWbemLevel1Login.RemRelease()
        tag = "windows-object-" + str(uuid.uuid4())

        # Copy from wmipersist.py
        # Install ActiveScriptEventConsumer
        activeScript, _ = iWbemServices.GetObject('ActiveScriptEventConsumer')
        activeScript = activeScript.SpawnInstance()
        activeScript.Name = tag
        activeScript.ScriptingEngine = 'VBScript'
        activeScript.CreatorSID = [1, 2, 0, 0, 0, 0, 0, 5, 32, 0, 0, 0, 32, 2, 0, 0]
        activeScript.ScriptText = vbs_content
        # Don't output verbose
        current=sys.stdout
        sys.stdout = StringIO()
        self.checkError('Adding ActiveScriptEventConsumer: %s' % tag,
                        iWbemServices.PutInstance(activeScript.marshalMe()))
        #result=sys.stdout.getvalue()
        sys.stdout = current

        if filer_Query is not None:
            eventFilter, _ = iWbemServices.GetObject('__EventFilter')
            eventFilter = eventFilter.SpawnInstance()
            eventFilter.Name = tag
            eventFilter.CreatorSID = [1, 2, 0, 0, 0, 0, 0, 5, 32, 0, 0, 0, 32, 2, 0, 0]
            eventFilter.Query = filer_Query
            eventFilter.QueryLanguage = 'WQL'
            eventFilter.EventNamespace = r'root\cimv2'
            # Don't output verbose
            current=sys.stdout
            sys.stdout = StringIO()
            self.checkError('Adding EventFilter: %s' % tag,
                iWbemServices.PutInstance(eventFilter.marshalMe()))
            sys.stdout = current

        else:
            # Timer
            wmiTimer, _ = iWbemServices.GetObject('__IntervalTimerInstruction')
            wmiTimer = wmiTimer.SpawnInstance()
            wmiTimer.TimerId = tag
            wmiTimer.IntervalBetweenEvents = int(timer)
            #wmiTimer.SkipIfPassed = False
            # Don't output verbose
            current=sys.stdout
            sys.stdout = StringIO()
            self.checkError('Adding IntervalTimerInstruction: %s' % tag,
                            iWbemServices.PutInstance(wmiTimer.marshalMe()))
            sys.stdout = current

            # EventFilter
            eventFilter,_ = iWbemServices.GetObject('__EventFilter')
            eventFilter =  eventFilter.SpawnInstance()
            eventFilter.Name = tag
            eventFilter.CreatorSID =  [1, 2, 0, 0, 0, 0, 0, 5, 32, 0, 0, 0, 32, 2, 0, 0]
            eventFilter.Query = 'select * from __TimerEvent where TimerID = "%s" ' % tag
            eventFilter.QueryLanguage = 'WQL'
            eventFilter.EventNamespace = r'root\subscription'
            # Don't output verbose
            current=sys.stdout
            sys.stdout = StringIO()
            self.checkError('Adding EventFilter: %s' % tag,
                iWbemServices.PutInstance(eventFilter.marshalMe()))
            sys.stdout = current

        # Binding EventFilter & EventConsumer
        filterBinding, _ = iWbemServices.GetObject('__FilterToConsumerBinding')
        filterBinding = filterBinding.SpawnInstance()
        filterBinding.Filter = '__EventFilter.Name="%s"' % tag
        filterBinding.Consumer = 'ActiveScriptEventConsumer.Name="%s"' % tag
        filterBinding.CreatorSID = [1, 2, 0, 0, 0, 0, 0, 5, 32, 0, 0, 0, 32, 2, 0, 0]
        # Don't output verbose
        current=sys.stdout
        sys.stdout = StringIO()
        self.checkError('Adding FilterToConsumerBinding',
                        iWbemServices.PutInstance(filterBinding.marshalMe()))
        sys.stdout = current
        
        iWbemServices.RemRelease()
        if returnTag == True: return tag

    def remove_Event(self, tag):
        iWbemServices = self.iWbemLevel1Login.NTLMLogin('//./root/subscription', NULL, NULL)
        self.iWbemLevel1Login.RemRelease()
        
        self.checkError('Removing ActiveScriptEventConsumer: %s' % tag,
                            iWbemServices.DeleteInstance('ActiveScriptEventConsumer.Name="%s"' % tag))

        self.checkError('Removing EventFilter: %s' % tag,
                        iWbemServices.DeleteInstance('__EventFilter.Name="%s"' % tag))

        self.checkError('Removing IntervalTimerInstruction: %s' % tag,
                        iWbemServices.DeleteInstance(
                            '__IntervalTimerInstruction.TimerId="%s"' % tag))

        self.checkError('Removing FilterToConsumerBinding',
                        iWbemServices.DeleteInstance(
                            r'__FilterToConsumerBinding.Consumer="ActiveScriptEventConsumer.Name=\"%s\"",'
                            r'Filter="__EventFilter.Name=\"%s\""' % (
                            tag, tag)))
        iWbemServices.RemRelease()
