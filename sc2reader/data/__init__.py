from __future__ import absolute_import

import json
import pkgutil
from sc2reader.log_utils import loggable

ABIL_LOOKUP = dict()
for entry in pkgutil.get_data('sc2reader.data', 'ability_lookup.csv').decode('utf-8').split('\n'):
    if not entry: continue
    str_id, abilities = entry.split(',',1)
    ABIL_LOOKUP[str_id] = abilities.split(',')

UNIT_LOOKUP = dict()
for entry in pkgutil.get_data('sc2reader.data', 'unit_lookup.csv').decode('utf-8').split('\n'):
    if not entry: continue
    str_id, title = entry.strip().split(',')
    UNIT_LOOKUP[str_id] = title

unit_data = pkgutil.get_data('sc2reader.data', 'unit_info.json').decode('utf-8')
unit_lookup = json.loads(unit_data)

command_data = pkgutil.get_data('sc2reader.data', 'train_commands.json').decode('utf-8')
train_commands = json.loads(command_data)

class Unit(object):

    def __init__(self, unit_id, flags):
        self.id = unit_id
        self.flags = flags
        self._type_class = None
        self.hallucinated = (flags & 2 == 2)

    def is_type(self, unit_type):
        if isinstance(unit_type, int):
            # Compare integer ids. Unknown units have id==0 and should be equal
            return self._type_class.id if self._type_class else unit_type == 0
        else:
            return self._type_class == unit_type

    @property
    def name(self):
        return self._type_class.name if self._type_class else None

    @property
    def title(self):
        return self._type_class.title if self._type_class else None

    @property
    def type(self):
        """ For backwards compatibility this returns the int id instead of the actual class """
        return self._type_class.id if self._type_class else None

    @property
    def race(self):
        return self._type_class.race if self._type_class else None

    @property
    def minerals(self):
        return self._type_class.minerals if self._type_class else None

    @property
    def vespene(self):
        return self._type_class.vespene if self._type_class else None

    @property
    def supply(self):
        return self._type_class.supply if self._type_class else None

    @property
    def is_worker(self):
        return self._type_class.is_worker if self._type_class else False

    @property
    def is_building(self):
        return self._type_class.is_building if self._type_class else False

    @property
    def is_army(self):
        return self._type_class.is_army if self._type_class else False

    def __str__(self):
        return "{0} [{1:X}]".format(self.name, self.id)

    def __cmp__(self, other):
        return cmp(self.id, other.id)

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return str(self)


class Ability(object):
    pass

@loggable
class Build(object):
    def __init__(self, build_id):
        self.id=build_id
        self.units = dict()
        self.abilities = dict()

    def create_unit(self, unit_id, unit_type, unit_flags):
        unit = Unit(unit_id, unit_flags)
        self.change_type(unit, unit_type)
        return unit

    def change_type(self, unit, new_type):
        if new_type in self.units:
            reference_unit = self.units[new_type]
            unit._type_class = reference_unit
        else:
            self.logger.error("Unable to change type of {0} to {1}; unit type not found in build {2}".format(unit,hex(new_type),self.id))

    def add_ability(self, ability_id, name, title=None, is_build=False, build_time=None, build_unit=None):
        ability = type(str(name),(Ability,), dict(
            id=ability_id,
            name=name,
            title=title or name,
            is_build=is_build,
            build_time=build_time,
            build_unit=build_unit
        ))
        setattr(self, name, ability)
        self.abilities[ability_id] = ability

    def add_unit_type(self, type_id, name, title=None, race='Neutral', minerals=0, vespene=0, supply=0, is_building=False, is_worker=False, is_army=False):
        unit = type(str(name),(Unit,), dict(
            id=type_id,
            name=name,
            title=title or name,
            race=race,
            minerals=minerals,
            vespene=vespene,
            supply=supply,
            is_building=is_building,
            is_worker=is_worker,
            is_army=is_army,
        ))
        setattr(self, name, unit)
        self.units[type_id] = unit

def load_build(expansion, version):
    build = Build(version)

    unit_file = '{0}/{1}_units.csv'.format(expansion,version)
    for entry in pkgutil.get_data('sc2reader.data', unit_file).decode('utf-8').split('\n'):
        if not entry: continue
        int_id, str_id = entry.strip().split(',')
        unit_type = int(int_id,10)
        title = UNIT_LOOKUP[str_id]

        values = dict(type_id=unit_type, name=title)
        for race in ('Protoss','Terran','Zerg'):
            if title.lower() in unit_lookup[race]:
                values.update(unit_lookup[race][title.lower()])
                values['race']=race
                break

        build.add_unit_type(**values)

    abil_file = '{0}/{1}_abilities.csv'.format(expansion,version)
    build.add_ability(ability_id=0, name='RightClick', title='Right Click')
    for entry in pkgutil.get_data('sc2reader.data', abil_file).decode('utf-8').split('\n'):
        if not entry: continue
        int_id_base, str_id = entry.strip().split(',')
        int_id_base = int(int_id_base,10) << 5

        abils = ABIL_LOOKUP[str_id]
        real_abils = [(i,abil) for i,abil in enumerate(abils) if abil.strip()!='']

        if len(real_abils)==0:
            real_abils = [(0, str_id)]

        for index, ability_name in real_abils:
            unit_name, build_time = train_commands.get(ability_name, ('', 0))
            if 'Hallucinated' in unit_name: # Not really sure how to handle hallucinations
                unit_name = unit_name[12:]

            build.add_ability(
                ability_id=int_id_base | index,
                name=ability_name,
                is_build=bool(unit_name),
                build_unit=getattr(build, unit_name, None),
                build_time=build_time
            )

    return build

# Load the WoL Data
wol_builds = dict()
for version in ('16117','17326','18092','19458','22612','24944'):
    wol_builds[version] = load_build('WoL', version)

# Load HotS Data
hots_builds = dict()
for version in ('base','23925','24247','24764'):
    hots_builds[version] = load_build('HotS', version)

builds = {'WoL':wol_builds,'HotS':hots_builds}

