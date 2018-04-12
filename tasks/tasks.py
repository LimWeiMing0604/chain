from celery import Celery, platforms

platforms.C_FORCE_ROOT = True
from  chain import settings
app = Celery('chain')
app.config_from_object('django.conf:settings',)
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
import logging,json
logger = logging.getLogger('tasks')

from multiprocessing import current_process
from tasks.ansible_2420.runner import AdHocRunner, PlayBookRunner
from tasks.ansible_2420.inventory import BaseInventory

from asset.models import asset


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))



@app.task()
def  ansbile_tools(assets,tools,module):
    current_process()._config = {'semprefix': '/mp'}

    hostname = []
    for i in assets:
        hostname.append(i['hostname'])
    inventory = BaseInventory(assets)
    retsult_data = []

    if   module == "script":
        runner = AdHocRunner(inventory)
        tasks = [
            {"action": {"module": "{}".format(module), "args": "{}".format(tools)}, "name": "script"},
        ]
        retsult = runner.run(tasks, "all")

        try:
            ok = retsult.results_raw['ok']
            failed = retsult.results_raw['failed']
            unreachable = retsult.results_raw['unreachable']
            if not ok and not failed:
                ret = unreachable
            elif not ok:
                ret = failed
            else:
                ret = ok
        except Exception as e:
            logger.error("{}".format(e))

        for i in range(len(hostname)):
            std = []
            ret_host = {}
            n = hostname[i]
            try:
                out = ret[n]['script']['stdout']
                err = ret[n]['script']['stderr']
                std.append("{0}{1}".format(out, err))
            except Exception as e:
                    logger.error(e)
                    try:
                        std.append("{0} \n".format(ret[n]['script']['msg']))
                    except Exception as e:
                        logger.error("执行失败{0}".format(e))
            ret_host['hostname'] = n
            ret_host['data'] = '\n'.join(std)
            retsult_data.append(ret_host)

    elif  module == 'yml':

            runers = PlayBookRunner(playbook_path=tools, inventory=inventory)
            retsult = runers.run()

            try:
                ret = retsult['results_callback']
            except Exception as e:
                logger.error("{}".format(e))

            for i in range(len(hostname)):
                    std = []
                    ret_host = {}
                    n = hostname[i]
                    try:
                        print(ret)
                        out = ret[n]['stdout']
                        err = ret[n]['stderr']
                        std.append("{0}{1}".format(out, err))
                    except Exception as e:
                        logger.error(e)
                        try:
                            std.append("{0} \n".format(ret[n]['msg']))
                        except Exception as e:
                            logger.error("执行失败{0}".format(e))
                    ret_host['hostname'] = n
                    ret_host['data'] = '\n'.join(std)
                    retsult_data.append(ret_host)

    return   retsult_data

@app.task()
def  ansbile_asset_hardware(id,assets):
        current_process()._config = {'semprefix': '/mp'}

        inventory = BaseInventory(assets)
        runner = AdHocRunner(inventory)
        tasks = [
               {"action": {"module": "setup", "args": ""}, "name": "script"},
        ]
        retsult = runner.run(tasks, "all")
        hostname = assets[0]['hostname']

        print(retsult.results_raw['ok'][hostname])


        try:
            data = retsult.results_raw['ok'][hostname]['script']['ansible_facts']
            nodename = data['ansible_nodename']
            disk = "{}".format(str(sum([int(data["ansible_devices"][i]["sectors"]) * \
                                           int(data["ansible_devices"][i]["sectorsize"]) / 1024 / 1024 / 1024 \
                                           for i in data["ansible_devices"] if
                                           i[0:2] in ("vd", "ss", "sd")])) + str(" GB"))
            mem = int(data['ansible_memtotal_mb'] / 1024)
            cpu = int("{}".format(
                data['ansible_processor_count'] * data["ansible_processor_cores"]))

            system = data['ansible_product_name']+" "+data['ansible_lsb']["description"]

            obj = asset.objects.filter(id=id).update(hostname=nodename,
                                                     disk=disk,
                                                     memory=mem,
                                                     cpu=cpu,
                                                     system=system)

        except Exception as e:
            logger.error(e)






