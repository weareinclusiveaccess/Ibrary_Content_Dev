# Essential Biology Extraction Review Guide

This folder contains chapter-level JSON exports for the Essential Biology textbook.
Use this guide to review chapter completeness and structure consistency.

## How to review a chapter

1. Open the chapter JSON file for the chapter number you are reviewing.
2. Confirm top-level keys exist and are non-empty where expected:
   - `chapter_number`, `chapter_title`, `chapter_page_label`
   - `outline`, `prerequisites`, `introduction`
   - `subtopics_info` (array)
   - `tables_info` (object, empty when no tables)
   - `figures_info` (array)
   - `chapter_summary` (string, empty if placeholder)
   - `chapter_exercises` (object with placeholder arrays if not populated)
3. For each entry in `subtopics_info`,:
   - `learning_outcomes`, `subtopic_introduction`
   - `subtopic_number`, `subtopic_title`, `subtopic_page_label`
   - `subtopic_assessments`, `subtopic_concept`, `subtopic_summary`
   - `subsubtopics_info` (array; empty if none)
4. For each entry in `subsubtopics_info`,:
   - `subsubtopic_title`
   - `subsubtopic_start_page_label`, `subsubtopic_end_page_label`
   - `subsubtopic_page_contents`
5. Spot-check that page labels and content align with the PDF page range
   for the chapter.

## Structural examples

### figures_info (lines 31-50)
Each figure is an object in the `figures_info` array.
```
{
  "chapter_number": "2",
  "figure_number": "2.7",
  "figure_title": "Formation of sodium chloride.",
  "figure_description": "This is the description provided in the textbook. Ensure it is exact.",
  "figure_content": {
    "figure_url": "artifacts/images/chapter_2_Formation_of_sodium_chloride.png",
    "accessible_description": "Step-by-step explanation of electron transfer and ionic bonding.",
    "formation_of_sodium_chloride": {
      "step_1": {
        "description": "Sodium atom (Na) and Chlorine atom (Cl)",
        "details": "Sodium has one electron in its outer shell, while chlorine has seven."
      }
    }
  }
}
```

### tables_info (lines 52-68)
`tables_info` is an object keyed by table number. Each table entry is an object.
```
{
  "2.1": {
    "table_number": "2.1",
    "table_title": "Properties of Water",
    "table": [
      {
        "column1": "Water is a solvent",
        "column2": "Polarity",
        "column3": "Water facilitates chemical reactions"
      }
    ]
  }
}
```

### formulas_and_reactions (lines 70-72)
If present, this should be an array of formula or reaction records. See
[`2_The_Chemical_Basis_of_Life_20260117_extracted.json`](./2_The_Chemical_Basis_of_Life_20260117_extracted.json)
for samples.

### connections (lines 74-83)
If present, this should be an array of connection notes (contextual callouts).
```
[
  {
    "type": "Health",
    "title": "How does evolution affect me personally?",
    "content": "In the presence of an antibiotic, resistant bacteria..."
  }
]
```

### notes (lines 86-91)
If present, tiny notes at the bottom of some pages. This should be an array of
short note strings or note objects.
```
[
  "To specify an organism, use the full binomial name.", 
]
```

## Tips

- Keep placeholders as empty strings/arrays until populated.
- Preserve existing keys even if the content is empty.
- Avoid changing capitalization or punctuation in extracted text unless fixing
  obvious OCR errors.
- Use [`1_Biology_The_Science_of_Life_20260117_extracted.json`](./1_Biology_The_Science_of_Life_20260117_extracted.json) and
  [`2_The_Chemical_Basis_of_Life_20260117_extracted.json`](./2_The_Chemical_Basis_of_Life_20260117_extracted.json) as samples.
