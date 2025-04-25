import os
from pathlib import Path
from collections import defaultdict
from copr.v3 import Client


def get_repo_info():
    """从环境变量中提取 distro、version 和 project 名称"""
    repo = os.environ["GITHUB_REPOSITORY"]
    ref = os.environ["GITHUB_REF_NAME"]

    parts = repo.split("/")[1].split("-")
    distro = parts[0]                # e.g. "fedora"
    project = "-".join(parts[1:])    # e.g. "rpm-rebuild"
    version = ref.strip()            # e.g. "42"

    return distro, version, project


def is_dry_run():
    """检查是否为干运行"""
    return os.environ.get("DRYRUN", "false").lower() == "true"


def all_builds_finished(client, owner, project):
    """是否所有构建任务都已经结束"""
    builds = client.build_proxy.get_list(owner, project)
    return all(b.state in ("succeeded", "forked", "skipped") for b in builds)


def group_and_select_builds(builds, prefix):
    grouped = defaultdict(list)
    """分组并选择要删除的构建"""
    for build in builds:
        if not any(chroot.startswith(prefix) for chroot in build["chroots"]):
            continue

        version = build["source_package"]["version"]
        chroots = tuple(sorted(build["chroots"]))
        grouped[(version, chroots)].append(build)

    deletions = []

    for (version, chroots), group in grouped.items():
        succeeded = [b for b in group if b["state"] == "succeeded"]
        failed = [b for b in group if b["state"] == "failed"]
        keep_ids = set()

        if succeeded and not failed:
            latest_success = max(succeeded, key=lambda b: b["submitted_on"])
            keep_ids.add(latest_success["id"])
        elif failed and not succeeded:
            latest_fail = max(failed, key=lambda b: b["submitted_on"])
            keep_ids.add(latest_fail["id"])
        elif succeeded and failed:
            latest_success = max(succeeded, key=lambda b: b["submitted_on"])
            latest_fail = max(failed, key=lambda b: b["submitted_on"])
            keep_ids.add(latest_success["id"])
            if latest_fail["submitted_on"] > latest_success["submitted_on"]:
                keep_ids.add(latest_fail["id"])

        for b in group:
            if b["id"] not in keep_ids:
                deletions.append(b["id"])

    return deletions


def get_packages_list():
    return [p.stem for p in Path("SPECS-PATCHES").rglob("*.patch")]


def main():
    client = Client.create_from_config_file("copr-api")
    owner = client.config["username"]
    distro, version, project = get_repo_info()

    if not all_builds_finished(client, owner, project):
        print("::warning::❗ Skip cleanup: project has unfinished builds.")
        return

    packages = get_packages_list()
    total_deletions = []

    for pkg in packages:
        try:
            builds = client.build_proxy.get_list(owner, project, pkg)
            deletions = group_and_select_builds(builds, f"{distro}-{version}")
            if deletions:
                print(f"🔸 Delete: {pkg} -> {deletions}")
                total_deletions.extend(deletions)
        except Exception as e:
            print(f"::warning::⚠️ Failed to get builds for {pkg}: {e}")

    if total_deletions:
        if is_dry_run():
            print(f"::notice::🔍 Dry run: would delete {total_deletions}")
            return

        client.build_proxy.delete_list(total_deletions)
        print(f"::notice::✅ Deleted builds: {total_deletions}")
    else:
        print("::notice::✅ No builds to delete.")


if __name__ == "__main__":
    main()
