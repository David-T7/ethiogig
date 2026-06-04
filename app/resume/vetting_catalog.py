"""
Stack definitions for candidate vetting assessments.
`category` keys must match Services.name (case-insensitive) in the main database.
"""

MIN_TECHNOLOGIES_TO_PASS = 2

# Each stack lists technologies the candidate must prove (theory + practical per tech).
STACKS_BY_CATEGORY = {
    'landing page development': [
        {
            'slug': 'react-developer',
            'name': 'React Developer',
            'description': 'React, JavaScript, HTML, and CSS for landing pages.',
            'technologies': ['React', 'JavaScript', 'HTML', 'CSS'],
        },
        {
            'slug': 'frontend-fundamentals',
            'name': 'Frontend Fundamentals',
            'description': 'Core web skills for page layout and interactivity.',
            'technologies': ['JavaScript', 'HTML', 'CSS'],
        },
    ],
    'web application interface development': [
        {
            'slug': 'react-developer',
            'name': 'React Developer',
            'description': 'UI components and client-side application logic.',
            'technologies': ['React', 'JavaScript', 'HTML', 'CSS'],
        },
        {
            'slug': 'fullstack-javascript',
            'name': 'Full Stack JavaScript',
            'description': 'End-to-end product interfaces with a JS stack.',
            'technologies': ['JavaScript', 'React', 'Node.js', 'PostgreSQL'],
        },
    ],
    'frontend developer': [
        {
            'slug': 'react-developer',
            'name': 'React Developer',
            'description': 'React, JavaScript, HTML, and CSS fundamentals.',
            'technologies': ['React', 'JavaScript', 'HTML', 'CSS'],
        },
        {
            'slug': 'frontend-fundamentals',
            'name': 'Frontend Fundamentals',
            'description': 'Core web building blocks without a specific framework.',
            'technologies': ['JavaScript', 'HTML', 'CSS'],
        },
    ],
    'backend developer': [
        {
            'slug': 'node-developer',
            'name': 'Node.js Developer',
            'description': 'Server-side JavaScript and APIs.',
            'technologies': ['Node.js', 'JavaScript', 'Express', 'MongoDB'],
        },
        {
            'slug': 'python-backend',
            'name': 'Python Backend Developer',
            'description': 'Python APIs and data layers.',
            'technologies': ['Python', 'Django', 'PostgreSQL'],
        },
    ],
    'full stack developer': [
        {
            'slug': 'mern-developer',
            'name': 'MERN Developer',
            'description': 'MongoDB, Express, React, and Node.js.',
            'technologies': ['MongoDB', 'Express', 'React', 'Node.js'],
        },
        {
            'slug': 'fullstack-javascript',
            'name': 'Full Stack JavaScript',
            'description': 'End-to-end JavaScript product development.',
            'technologies': ['JavaScript', 'React', 'Node.js', 'PostgreSQL'],
        },
    ],
    'mobile developer': [
        {
            'slug': 'react-native-developer',
            'name': 'React Native Developer',
            'description': 'Cross-platform mobile with React Native.',
            'technologies': ['React Native', 'JavaScript', 'TypeScript'],
        },
        {
            'slug': 'mobile-fundamentals',
            'name': 'Mobile Fundamentals',
            'description': 'Mobile UI and platform basics.',
            'technologies': ['JavaScript', 'React Native'],
        },
    ],
    'data scientist': [
        {
            'slug': 'python-data',
            'name': 'Python Data Stack',
            'description': 'Python, SQL, and data analysis.',
            'technologies': ['Python', 'SQL', 'Pandas'],
        },
    ],
    'devops engineer': [
        {
            'slug': 'cloud-devops',
            'name': 'Cloud DevOps',
            'description': 'Linux, Docker, and cloud deployment.',
            'technologies': ['Linux', 'Docker', 'AWS'],
        },
    ],
}

DEFAULT_STACKS = [
    {
        'slug': 'general-developer',
        'name': 'General Developer',
        'description': 'Core programming skills for your role.',
        'technologies': ['JavaScript', 'Git', 'SQL'],
    },
]


def normalize_category(name):
    return (name or '').strip().lower()


def stacks_for_position(position_name):
    key = normalize_category(position_name)
    stacks = STACKS_BY_CATEGORY.get(key)
    if stacks:
        return stacks
    for catalog_key, catalog_stacks in STACKS_BY_CATEGORY.items():
        if key in catalog_key or catalog_key in key:
            return catalog_stacks
    return DEFAULT_STACKS


def technologies_for_stack(stack_slug, position_name):
    for stack in stacks_for_position(position_name):
        if stack['slug'] == stack_slug:
            return stack['technologies']
    return []
