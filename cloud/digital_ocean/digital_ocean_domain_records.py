import os
import time

try:
    from dopy.manager import DoError, DoManager
    HAS_DOPY = True
except ImportError as e:
    HAS_DOPY = False

class TimeoutError(DoError):
    def __init__(self, msg, id):
        super(TimeoutError, self).__init__(msg)
        self.id = id

class JsonfyMixIn(object):
    def to_json(self):
        return self.__dict__

class DomainRecord(JsonfyMixIn):
    manager = None

    def __init__(self, json):
        self.__dict__.update(json)
    update_attr = __init__

    def update(self, data = None, record_type = None):
        json = self.manager.edit_domain_record(self.domain_id,
                                               self.id,
                                               record_type if record_type is not None else self.record_type,
                                               data if data is not None else self.data)
        self.__dict__.update(json)
        return self

    def destroy(self):
        json = self.manager.destroy_domain_record(self.domain_id, self.id)
        return json

class Domain(JsonfyMixIn):
    manager = None

    def __init__(self, domain_json):
        self.__dict__.update(domain_json)

    def destroy(self):
        self.manager.destroy_domain(self.id)

    def records(self):
        json = self.manager.all_domain_records(self.id)
        return map(DomainRecord, json)

    @classmethod
    def add(cls, name, ip):
        json = cls.manager.new_domain(name, ip)
        return cls(json)

    @classmethod
    def setup(cls, api_token):
        cls.manager = DoManager(None, api_token, api_version=2)
        DomainRecord.manager = cls.manager

    @classmethod
    def list_all(cls):
        domains = cls.manager.all_domains()
        return map(cls, domains)

    @classmethod
    def find(cls, name=None, id=None):
        if name is None and id is None:
            return False

        domains = Domain.list_all()

        if id is not None:
            for domain in domains:
                if domain.id == id:
                    return domain

        if name is not None:
            for domain in domains:
                if domain.name == name:
                    return domain

        return False

def core(module):
    def getkeyordie(k):
        v = module.params[k]
        if v is None:
            module.fail_json(msg='Unable to load %s' % k)
        return v

    try:
        api_token = module.params['api_token'] or os.environ['DO_API_TOKEN'] or os.environ['DO_API_KEY']
    except KeyError as e:
        module.fail_json(msg='Unable to load %s' % e.message)

    changed = True
    state = module.params['state']

    Domain.setup(api_token)
    if state in ('present'):
        domain = Domain.find(id=module.params["id"])

        if not domain:
            domain = Domain.find(name=getkeyordie("name"))

        if not domain:
            domain = Domain.add(getkeyordie("name"),
                                getkeyordie("ip"))
            module.exit_json(changed=True, domain=domain.to_json())
        else:
            records = domain.records()
            at_record = None
            for record in records:
                if record.name == "@" and record.record_type == 'A':
                    at_record = record

            if not at_record.data == getkeyordie("ip"):
                record.update(data=getkeyordie("ip"), record_type='A')
                module.exit_json(changed=True, domain=Domain.find(id=record.domain_id).to_json())

        module.exit_json(changed=False, domain=domain.to_json())

    elif state in ('absent'):
        domain = None
        if "id" in module.params:
            domain = Domain.find(id=module.params["id"])

        if not domain and "name" in module.params:
            domain = Domain.find(name=module.params["name"])

        if not domain:
            module.exit_json(changed=False, msg="Domain not found.")

        event_json = domain.destroy()
        module.exit_json(changed=True, event=event_json)


def main():
    module = AnsibleModule(
        argument_spec = dict(
            state = dict(choices=['present', 'absent'], default='present'),
            api_token = dict(aliases=['API_TOKEN'], no_log=True),
            name = dict(type='str'),
            id = dict(aliases=['droplet_id'], type='int'),
            ip = dict(type='str'),
            type = dict(type='str')
        ),
        required_one_of = (
            ['id', 'name'],
        ),
    )
    if not HAS_DOPY:
        module.fail_json(msg='dopy required for this module')

    try:
        core(module)
    except TimeoutError as e:
        module.fail_json(msg=str(e), id=e.id)
    except (DoError, Exception) as e:
        module.fail_json(msg=str(e))

# import module snippets
from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
