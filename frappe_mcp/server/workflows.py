"""Per-request skill discovery and resource reads for Frappe applications."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import quote

SKILLS = 'io.modelcontextprotocol/skills'


@dataclass(frozen=True)
class Skill:
    """Static workflow files. The visibility callback runs in the current request."""

    name: str
    description: str
    resources: tuple[tuple[str, str, str], ...]
    visible: Callable[[], bool]

    @classmethod
    def build(cls, name, description, instructions, files, visible):
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64:
            raise ValueError('Invalid skill name')
        if (
            not description.strip()
            or len(description) > 1024
            or not instructions.strip()
        ):
            raise ValueError('Skill requires a description and instructions')
        markdown = f'---\nname: {json.dumps(name)}\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n\n{instructions}\n'
        values = {'SKILL.md': markdown}
        for path, content in (files or {}).items():
            parts = path.split('/')
            if path in values or any(p in ('', '.', '..') or '\\' in p for p in parts):
                raise ValueError('Invalid skill file path')
            values[path] = content
        if (
            len(values) > 512
            or sum(len(content.encode()) for content in values.values())
            > 16 * 1024 * 1024
        ):
            raise ValueError('Skill exceeds portable size limits')
        return cls(
            name,
            description,
            tuple(
                (
                    f'skill://{name}/{quote(path)}',
                    'text/markdown' if path.endswith('.md') else 'text/plain',
                    text,
                )
                for path, text in values.items()
            ),
            visible,
        )

    def manifest(self):
        files = []
        for uri, _, text in self.resources:
            content = text.encode()
            files.append(
                {
                    'uri': uri,
                    'size': len(content),
                    'digest': 'sha256:' + hashlib.sha256(content).hexdigest(),
                }
            )
        return {
            'uri': self.resources[0][0],
            'frontmatter': {'name': self.name, 'description': self.description},
            'resources': files,
        }


class Workflows:
    def __init__(self):
        self.skills: dict[str, Skill] = {}

    def add(
        self,
        name: str,
        description: str,
        instructions: str,
        *,
        files: Mapping[str, str] | None = None,
        visible: Callable[[], bool] = lambda: True,
    ):
        if name in self.skills:
            raise ValueError('Duplicate skill name')
        self.skills[name] = Skill.build(name, description, instructions, files, visible)

    def handle(self, method, params):
        if 'cursor' in params:
            raise ValueError('Unknown cursor')
        skills = [skill for _, skill in sorted(self.skills.items()) if skill.visible()]
        uri = params.get('uri')
        if method == 'skills/list':
            return {'skills': [skill.manifest() for skill in skills]}
        if method == 'skills/get':
            for skill in skills:
                if skill.resources[0][0] == uri:
                    return {'skill': skill.manifest()}
        if method == 'resources/templates/list':
            return {'resourceTemplates': []}
        if method == 'resources/list':
            resources = []
            for skill in skills:
                for index, (address, mime, _) in enumerate(skill.resources):
                    resources.append(
                        {
                            'uri': address,
                            'mimeType': mime,
                            'name': skill.name
                            if index == 0
                            else address.rsplit('/', 1)[1],
                        }
                    )
            return {'resources': resources}
        if method == 'resources/read':
            for skill in skills:
                for address, mime, content in skill.resources:
                    if address == uri:
                        return {
                            'contents': [
                                {'uri': uri, 'mimeType': mime, 'text': content}
                            ]
                        }
        raise ValueError('Resource or workflow unavailable')
