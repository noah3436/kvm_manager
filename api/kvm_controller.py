import libvirt
import os
from xml.etree import ElementTree

def connect():
    return libvirt.open('qemu:///system')

def create_vm(vm_name, iso_path, user):
    conn = connect()
    xml = f"""<domain type='kvm'>
      <name>{vm_name}</name>
      <memory unit='MiB'>512</memory>
      <vcpu>1</vcpu>
      <os>
        <type arch='x86_64'>hvm</type>
        <boot dev='cdrom'/>
      </os>
      <devices>
        <disk type='file' device='cdrom'>
          <source file='{iso_path}'/>
          <target dev='hdc' bus='ide'/>
          <readonly/>
        </disk>
        <graphics type='vnc' port='-1'/>
      </devices>
    </domain>"""
    conn.defineXML(xml)
    conn.lookupByName(vm_name).create()
    conn.close()

def power_off_vm(vm_name):
    conn = connect()
    dom = conn.lookupByName(vm_name)
    dom.shutdown()
    conn.close()

def delete_vm(vm_name):
    conn = connect()
    dom = conn.lookupByName(vm_name)
    dom.destroy()
    dom.undefine()
    conn.close()
