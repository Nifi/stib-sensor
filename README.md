# Stib-sensor
This code is a custom component to integrate the Stib (the Brussels public transport) info in Home Assistant.
This component adds sensors with the next passages in minutes in real-time for a line at a given stop.

## Install

Copy these files to custom_components/stib/

Then configure the sensors by setting up the stib platform in `configuration.yaml`.

## Options

| Name | Type | Requirement | Description
| ---- | ---- | ------- | -----------
| platform | string | **Required** | `stib`
| api_key | string | **Required** | The access token generated at opendata.stib-mivb.be.
| language | string | **Optional** | The language of the stop names: 'fr' or 'nl'. By default: 'fr'
| stops | object | **Required** | List of stops to display next passages of.

**Example:**

```yaml
sensor:
  - platform: stib
    api_key: '< STIB access token from opendata.stib-mivb.be >'
    stops:
      - 8021
      - 8022
```

By default the stop names are in French, but the stop names can be in Dutch by specifying the language.

## Info
### How to get the stop ids?

Go to http://www.stib-mivb.be/horaires-dienstregeling2.html, select the line, the destination and then the stop name.
The stop id can be found at the end of the url after `_stop=`.

For example, for line 1 with direction 'Gare de l'Ouest' at 'Gare Centrale', the url is: `http://www.stib-mivb.be/horaires-dienstregeling2.html?l=fr&_line=1&_directioncode=V&_stop=8021`.
The stop id is then 8021.

Get the id for each stop you need and add them to your configuration.

### How are the sensors represented?

For each line that passes at a given station you get a new sensor following this format: `stib_[stop]_[line]`.

For example with stop id 8021 you get these two sensors:
- ` sensor.stib_8021_1`
- ` sensor.stib_8021_5`

The state returns the waiting time for the next vehicles : 

```text
sensor.stib_8021_1      5 (Gare De L'Ouest) - 15 (Gare De L'Ouest)
```

Other attributes are :
```json
{
  "stop_name": Gare Centrale
  "next_departure": 5
  "next_destination": Gare De L'Ouest
  "upcoming_departure": 15
  "upcoming_destination": Gare De L'Ouest
  "line": 1
  "attribution": Data provided by opendata-api.stib-mivb.be
  "friendly_name": stib 8021  1
  "icon": mdi:bus
}
```


