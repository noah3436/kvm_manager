import libvirt
import json
import subprocess
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import os

# Trang chủ
@csrf_exempt
def home(request):
    return render(request, 'home.html')


# Ánh xạ cấu hình
def get_config(config_name):
    return {
        'low':    {'cpu': 1, 'ram': 1024, 'disk': '5G'},
        'medium': {'cpu': 2, 'ram': 2048, 'disk': '10G'},
        'high':   {'cpu': 4, 'ram': 4096, 'disk': '20G'},
    }.get(config_name)


# Tìm cổng VNC trống
def get_free_vnc_port(start=5901, end=5999):
    for port in range(start, end):
        result = subprocess.run(["ss", "-ltn"], stdout=subprocess.PIPE)
        if f":{port}" not in result.stdout.decode():
            return port
    raise Exception("Không tìm thấy cổng VNC trống")

# Khởi động websockify để tạo link VNC
def start_novnc(vnc_port, web_port):
    subprocess.Popen([
        "websockify",
        f"{web_port}",
        f"localhost:{vnc_port}",
        "--web=/usr/share/novnc",
        "--daemon"
    ])

@csrf_exempt
def create_vm(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        template = data.get('template')

        iso_map = {
            'ubuntu': '/var/lib/libvirt/images/ubuntu-20.04.iso',
            'centos': '/var/lib/libvirt/images/CentOS-7.iso',
            'debian': '/var/lib/libvirt/images/debian-11.iso',
            'win7': '/var/lib/libvirt/images/win7.iso',
            'win10': '/var/lib/libvirt/images/win10.iso',
        }

        iso_path = iso_map.get(template)
        if not iso_path or not os.path.exists(iso_path):
            return JsonResponse({'error': 'Template không hợp lệ hoặc file ISO không tồn tại'}, status=400)

        try:
            disk_path = f"/var/lib/libvirt/images/{name}.qcow2"
            subprocess.run(["qemu-img", "create", "-f", "qcow2", disk_path, "15G"], check=True)

            vnc_port = get_free_vnc_port()
            web_port = 6000 + (vnc_port - 5900)

            xml = f"""
            <domain type='kvm'>
              <name>{name}</name>
              <memory unit='MiB'>1024</memory>
              <vcpu>1</vcpu>
              <os>
                <type arch='x86_64' machine='pc'>hvm</type>
                <boot dev='cdrom'/>
              </os>
              <devices>
                <disk type='file' device='disk'>
                  <driver name='qemu' type='qcow2'/>
                  <source file='{disk_path}'/>
                  <target dev='vda' bus='virtio'/>
                </disk>
                <disk type='file' device='cdrom'>
                  <driver name='qemu' type='raw'/>
                  <source file='{iso_path}'/>
                  <target dev='hdc' bus='ide'/>
                  <readonly/>
                </disk>
                <graphics type='vnc' port='{vnc_port}' listen='0.0.0.0'/>
              </devices>
            </domain>
            """

            conn = libvirt.open('qemu:///system')
            dom = conn.defineXML(xml)
            dom.create()
            conn.close()

            start_novnc(vnc_port, web_port)

            return JsonResponse({
                'message': f'VM {name} đã được tạo từ {template}.',
                'vnc_url': f"http://{request.get_host().split(':')[0]}:{web_port}/vnc.html?host={request.get_host().split(':')[0]}&port={web_port}"
            })
        except libvirt.libvirtError as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Phương thức không hợp lệ'}, status=405)

# Liệt kê các VM
def list_vms(request):
    try:
        conn = libvirt.open('qemu:///system')
        vms = conn.listAllDomains()
        result = []
        for vm in vms:
            info = {'name': vm.name(), 'status': 'running' if vm.isActive() else 'shut off'}
            # Parse XML để lấy cổng VNC nếu có
            xml = vm.XMLDesc()
            if "<graphics" in xml:
                import re
                m = re.search(r"graphics[^>]+port='(\d+)'", xml)
                if m:
                    vnc_port = int(m.group(1))
                    info['vnc_port'] = vnc_port
                    info['web_port'] = 6000 + (vnc_port - 5900)
            result.append(info)
        conn.close()
        return JsonResponse({'vms': result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
# Xoá VM
@csrf_exempt
def delete_vm(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        try:
            conn = libvirt.open('qemu:///system')
            vm = conn.lookupByName(name)
            if vm.isActive():
                vm.destroy()
            vm.undefine()
            conn.close()
            disk_file = f"/var/lib/libvirt/images/{name}.qcow2"
            if os.path.exists(disk_file):
                os.remove(disk_file)
            return JsonResponse({'message': f'VM {name} đã bị xoá.'})
        except libvirt.libvirtError as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Phương thức không hợp lệ'}, status=405)
