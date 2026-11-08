import argparse
import re
from pathlib import Path


# Repartition Fedora's file lists without changing their RPM attributes.
INPUTS = {
    'main': 'main',
    'pam': 'main',
    'libs': 'libs',
    'shared': 'shared',
    'sysusers': 'sysusers',
    'devel': 'devel',
    'udev': 'udev',
    'container': 'container',
    'networkd': 'networkd',
    'resolve': 'resolve',
    'ukify': 'ukify',
    'boot': 'boot',
    'import-keys': 'import',
}

# Specific components precede the directories or facilities that contain them.
RULES = [
    ('zsh-completion', r'^/usr/share/zsh/site-functions/'),
    ('devel', r'^/usr/share/pkgconfig/(systemd|udev)\.pc$'),
    ('shared', r'^/usr/lib[^/]*/systemd$'),
    ('sysusers', r'/sysusers\.d/README$'),
    ('udev-kernelless', r'/systemd-pstore\.service\.d(/10-kernelless\.conf)?$'),
    ('udev', r'/systemd-coredump(-register|d)\.service(\.|$)|/50-coredump\.conf$'),
    ('main', r'coredump|oomctl|systemd-oom|oomd\.conf|org\.freedesktop\.oom1'),
    ('networkd', r'systemd-network-generator'),
    ('boot', r'systemd-bless-boot'),
    ('udev', r'systemd-binfmt|/binfmt\.d(/|\.|$)|/proc-sys-fs-binfmt_misc\.|'
             r'/dev-hugepages\.mount$|'
             r'systemd-pstore|/pstore\.conf'),
    ('clonesetup', r'systemd-clonesetup|/(clonetab\.|clonesetup\.target)'),
    ('quota', r'systemd-quotacheck|/quotaon(-root|@)\.service'),
    ('udev', r'systemd-kexec|/kexec\.target$'),
    ('volatile-root', r'systemd-volatile-root'),
    ('udev', r'systemd-(fstab-generator|remount-fs|validatefs)|'
             r'/systemd-(mount|umount)\.|/systemd-(mount|umount)$|'
             r'/20-systemd-stub\.conf$'),
    ('main', r'systemd-(getty-generator|sysctl)|'
             r'/(emergency|rescue)(\.|@)|/(getty(-pre)?)\.target|'
             r'/etc/systemd/system/getty\.target\.wants$|'
             r'^/etc/sysctl(\.conf|\.d(/|$))|^/usr/lib/sysctl\.d$|'
             r'/sysctl\.d/(README|50-default\.conf)$|/man5/sysctl\.d\.|'
             r'^/usr/lib/systemd/ntp-units\.d$|'
             r'/kernel-command-line\.7|/systemd\.(image-(filter|policy)|mstack)\.7'),
    ('report', r'systemd-report'),
    ('storage', r'storagectl|mount\.storage|systemd-storage-(block|fs)|io\.systemd\.storage'),
    ('image', r'systemd-(dissect|mstack|loop|vpick)|mount\.(ddi|mstack)|'
              r'/90-image-dissect\.rules$'),
    ('boot-tools', r'systemd-sysupdate-notify-bootctl'),
    ('pcr', r'systemd-sysupdate-notify-pcrlock'),
    ('sysext', r'systemd-sysupdate-notify-sysext'),
    ('resolve', r'resolvectl|nss_resolve|nss-resolve|dnssec-trust-anchors\.d|'
                r'systemd\.(dns-delegate|dnssd|rr\.5)|/systemd/resolv\.conf$'),
    ('networkd', r'/80-(6rd-tunnel|vm-vt|container-(vb|ve|vz)|namespace-ns(-tun)?)\.link$'),
    ('containerized', r'/(console-getty|container-getty@)\.service|/systemd-container\.conf$'),
    ('pcr', r'systemd[.-]pcr|/pcrlock\.d(/|$)'),
    ('sysext', r'systemd-(confext|sysext)|io\.systemd\.sysext|(confext|sysext)\.conf|extension-release'),
    ('sysupdate', r'systemd-sysupdate|updatectl|sysupdate[.]|sysupdate1'),
    ('boot-tools', r'bootctl|systemd-(sbsign|measure|keyutil)'),
    ('stub', r'[^/]+\.efi\.stub|/(sd-stub|systemd-stub)\.'),
    ('boot', r'systemd-boot-(clear-sysfail|random-seed|update)|^/usr/lib/systemd/boot$'),
    ('capsule', r'/capsule(@|\.slice)'),
    ('credentials', r'credstore|systemd-creds|io\.systemd\.credentials'),
    ('debug', r'systemd-debug-generator|/breakpoint-|/debug-shell\.service|sys-kernel-(debug|tracing)\.mount'),
    ('udev', r'^/usr/share/factory/etc/vconsole\.conf$'),
    ('main', r'^/usr/share/factory(/|$)'),
    ('factory', r'factory-reset|systemd-tpm2-clear'),
    ('firstboot', r'systemd-firstboot|/first-boot-complete\.target$|'
                  r'/systemd-random-seed\.service\.d(/10-firstboot\.conf)?$'),
    ('sysinstall', r'systemd-sysinstall|io\.systemd\.sysinstall|/system-install\.target(\.wants)?$'),
    ('home', r'homectl|systemd-home|pam_systemd_home|homed\.conf|home1|/tmpfiles\.d/home\.conf$'),
    ('import', r'importctl|systemd-(import|export|pull)|oci-registry|org\.freedesktop\.import1|'
               r'/imports(-pre)?\.target|import-pubring'),
    ('namespace', r'systemd-(mountfsd|mountwork|nsresourced|nsresourcework)|'
                  r'io\.systemd\.(mount-file-system|namespace-resource)'),
    ('container', r'/var/lib/machines$|systemd-machined\.conf$|/tmpfiles\.d/systemd-nspawn\.conf$'),
    ('nspawn', r'systemd[.-]nspawn'),
    ('vmspawn', r'systemd-vmspawn'),
    ('storagetm', r'systemd-storagetm|/storage-target-mode\.target'),
    ('portable', r'portablectl|portabled|portable1|portables\.conf|^/var/lib/portables$|'
                 r'/systemd/(user/)?portable(/|$)'),
    ('ssh', r'^/etc/ssh(/|$)|/systemd/(ssh_config\.d|sshd_config\.d)(/|$)|systemd-ssh|/ssh-access\.target'),
    ('userdb', r'systemd-userdb|userdbctl|^/etc/userdb$'),
    ('mute-console', r'systemd(?:-|\\x2d)mute(?:-|\\x2d)console'),
    ('tpm2', r'^/usr/lib/nvpcr(/|$)|systemd-tpm2-(?!clear)|'
             r'/tpm2\.target'),
    ('cryptsetup', r'cryptsetup|cryptenroll|integritysetup|veritysetup|'
                   r'/(crypttab|integritytab|veritytab)\.|/etc/(crypttab|integritytab)$|'
                   r'pam_systemd_loadkey'),
    ('repart', r'systemd-(repart|growfs|makefs|mkswap)|/repart(/|\.|$)'),
    ('ukify', r'/man/[^/]+/ukify\.|/kernel/uki\.conf$|/boot/hwids(/|$)'),
    ('main', r'nss_myhostname|nss-myhostname|nss_systemd|nss-systemd'),
    ('udev',
     r'systemd-(battery-check|sysroot-fstab-check|time-wait-sync)|'
     r'/(bluetooth|printer|smartcard|sigpwr|time-set|time-sync|usb-gadget)\.target|'
     r'/(getty|serial-getty|modprobe)([.@-])|sys-kernel-config\.mount|'
     r'/sound\.target$|/static-nodes-permissions\.conf$|/sys-fs-fuse-connections\.mount$|'
     r'/systemd\.(link\.5|net-naming-scheme\.7)|/iocost\.conf\.5'),
]

# These entries are shared by the full and kernelless udev alternatives.
KERNELLESS = re.compile(
    r'^/usr/lib/sysctl\.d/|/timesyncd\.conf(?:\.|$)|'
    r'/(getty|serial-getty)@\.service|'
    r'systemd-binfmt|/binfmt\.d(/|\.|$)|/proc-sys-fs-binfmt_misc\.|'
    r'/dev-hugepages\.mount$|'
    r'/kexec\.target$|systemd-kexec|'
    r'systemd-pstore|/pstore\.conf|'
    r'systemd-(fstab-generator|gpt-auto-generator|remount-fs|validatefs|'
    r'coredump|fsck|random-seed|time-wait-sync|timesync)|'
    r'/systemd-(mount|umount)\.|/systemd-(mount|umount)$|'
    r'/20-systemd-stub\.conf$|'
    r'/(time-set|time-sync)\.target|^/var/lib/systemd/(random-seed|timesync)(/|$)|'
    r'org\.freedesktop\.timesync1'
)


def split_files(bootloader):
    rules = [(package, re.compile(pattern)) for package, pattern in RULES]
    outputs = {
        package: {}
        for package in {*INPUTS.values(), *(name for name, _ in RULES), 'udev-kernelless'}
    }

    for source, default in INPUTS.items():
        for line in Path(f'.file-list-{source}').read_text().splitlines():
            if not line.strip():
                continue
            path = line.rsplit(None, 1)[-1]
            package = next((name for name, pattern in rules if pattern.search(path)), default)
            if package == 'boot' and not bootloader:
                package = 'udev'
            if path in outputs[package] and outputs[package][path] != line:
                raise ValueError(f'Conflicting RPM attributes for {path}')
            outputs[package][path] = line

    outputs['udev-kernelless'].update({
        path: line for path, line in outputs['udev'].items() if KERNELLESS.search(path)
    })
    for package, entries in outputs.items():
        Path(f'.file-list-{package}').write_text(''.join(entries[path] + '\n' for path in sorted(entries)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Repartition Fedora's systemd file lists")
    parser.add_argument('--no-bootloader', action='store_true')
    split_files(not parser.parse_args().no_bootloader)
