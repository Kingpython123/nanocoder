# 评测集的基础镜像：slim 没有 git。pip 用清华镜像是因为开发环境在国内。
# 仓库以 git archive 复制进容器，没有 .git，用 setuptools_scm / hatch-vcs 的项目要靠 PRETEND_VERSION 才装得上。
FROM python:3.12-slim
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1 SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
RUN apt-get update -qq && apt-get install -y -qq git >/dev/null
