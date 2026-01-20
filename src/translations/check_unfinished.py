import xml.etree.ElementTree as ET

tree = ET.parse('tr.ts')
root = tree.getroot()

with open('unfinished_list.txt', 'w', encoding='utf-8') as f:
    f.write("Unfinished Translations:\n")
    f.write("-" * 30 + "\n")

    count = 0
    for context in root.findall('context'):
        for message in context.findall('message'):
            translation = message.find('translation')
            if translation is not None and translation.get('type') == 'unfinished':
                source = message.find('source').text
                if source:
                    f.write(f"- {source}\n")
                    count += 1

    f.write("-" * 30 + "\n")
    f.write(f"Total unfinished: {count}\n")
