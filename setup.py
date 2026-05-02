"""Setup configuration for Easinotate."""
from setuptools import setup, find_packages
from pathlib import Path

ROOT = Path(__file__).parent
README = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""

setup(
    name="easinotate",
    version="1.0.0",
    description="A modern Python image annotation framework with bounding-box drawing, "
                "labeling, folder-based categorization, and multi-format export.",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Easinotate",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "easinotate": ["resources/*.png", "resources/*.ico"],
    },














    
    python_requires=">=3.9",
    install_requires=[
        "PyQt6>=6.5,<7",
        "Pillow>=10.0",
    ],
    entry_points={
        "gui_scripts": [
            "easinotate = easinotate.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Topic :: Multimedia :: Graphics",
        "Topic :: Scientific/Engineering :: Image Recognition",
    ],
)
