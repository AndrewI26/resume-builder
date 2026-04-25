package resume

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
)

type Config struct {
	SectionVersions SectionVersions `json:"sectionVersions"`
	Composition     Composition     `json:"composition"`
}

type SectionVersions struct {
	Skills     []SkillsVersion     `json:"skills"`
	Experience []ExperienceVersion `json:"experience"`
	Projects   []ProjectsVersion   `json:"projects"`
	Education  []EducationVersion  `json:"education"`
}

type Composition struct {
	Name              string `json:"name"`
	SkillsVersion     string `json:"skillsVersion"`
	ExperienceVersion string `json:"experienceVersion"`
	ProjectsVersion   string `json:"projectsVersion"`
	EducationVersion  string `json:"educationVersion"`
}

type SkillsVersion struct {
	Name       string          `json:"name"`
	Categories []SkillCategory `json:"categories"`
}

type SkillCategory struct {
	Label string `json:"label"`
	Items string `json:"items"`
}

type ExperienceVersion struct {
	Name  string           `json:"name"`
	Items []ExperienceItem `json:"items"`
}

type ExperienceItem struct {
	Company    string   `json:"company"`
	CompanyURL string   `json:"companyURL"`
	DateRange  string   `json:"dateRange"`
	Role       string   `json:"role"`
	Location   string   `json:"location"`
	Highlights []string `json:"highlights"`
}

type ProjectsVersion struct {
	Name  string        `json:"name"`
	Items []ProjectItem `json:"items"`
}

type ProjectItem struct {
	Name       string   `json:"name"`
	URL        string   `json:"url"`
	TechStack  string   `json:"techStack"`
	DateRange  string   `json:"dateRange"`
	Highlights []string `json:"highlights"`
}

type EducationVersion struct {
	Name  string          `json:"name"`
	Items []EducationItem `json:"items"`
}

type EducationItem struct {
	Institution string   `json:"institution"`
	DateRange   string   `json:"dateRange"`
	Program     string   `json:"program"`
	Location    string   `json:"location"`
	AwardsLeft  []string `json:"awardsLeft"`
	AwardsRight []string `json:"awardsRight"`
}

type TemplateData struct {
	Skills struct {
		Categories []SkillCategory
	}
	Experience []ExperienceItem
	Projects   []ProjectItem
	Education  []EducationItem
}

func LoadConfig(path string) (Config, error) {
	var c Config
	b, err := os.ReadFile(path)
	if err != nil {
		return c, err
	}
	if err := json.Unmarshal(b, &c); err != nil {
		return c, err
	}
	return c, nil
}

func ResolveTemplateData(c Config) (TemplateData, error) {
	var out TemplateData

	if err := validateVersionNames(c.SectionVersions); err != nil {
		return out, err
	}
	if err := validateCompositionRefs(c); err != nil {
		return out, err
	}

	skillsByName := mapSkills(c.SectionVersions.Skills)
	expByName := mapExperience(c.SectionVersions.Experience)
	projByName := mapProjects(c.SectionVersions.Projects)
	eduByName := mapEducation(c.SectionVersions.Education)

	skills := skillsByName[c.Composition.SkillsVersion]
	experience := expByName[c.Composition.ExperienceVersion]
	projects := projByName[c.Composition.ProjectsVersion]
	education := eduByName[c.Composition.EducationVersion]

	if err := validateRequiredFields(experience, projects, education); err != nil {
		return out, err
	}

	out.Skills.Categories = skills.Categories
	out.Experience = experience.Items
	out.Projects = projects.Items
	out.Education = education.Items
	return out, nil
}

func validateVersionNames(v SectionVersions) error {
	if err := ensureUniqueNonEmptyNames("skills", listNamesSkills(v.Skills)); err != nil {
		return err
	}
	if err := ensureUniqueNonEmptyNames("experience", listNamesExperience(v.Experience)); err != nil {
		return err
	}
	if err := ensureUniqueNonEmptyNames("projects", listNamesProjects(v.Projects)); err != nil {
		return err
	}
	if err := ensureUniqueNonEmptyNames("education", listNamesEducation(v.Education)); err != nil {
		return err
	}
	return nil
}

func ensureUniqueNonEmptyNames(section string, names []string) error {
	seen := map[string]struct{}{}
	for _, n := range names {
		n = strings.TrimSpace(n)
		if n == "" {
			return fmt.Errorf("%s version name must be non-empty", section)
		}
		if _, ok := seen[n]; ok {
			return fmt.Errorf("duplicate %s version name %q", section, n)
		}
		seen[n] = struct{}{}
	}
	return nil
}

func validateCompositionRefs(c Config) error {
	missing := func(section, name string, names []string) error {
		for _, n := range names {
			if n == name {
				return nil
			}
		}
		return fmt.Errorf("composition %s %q not found in sectionVersions.%s", section, name, section)
	}

	if err := missing("skills", c.Composition.SkillsVersion, listNamesSkills(c.SectionVersions.Skills)); err != nil {
		return err
	}
	if err := missing("experience", c.Composition.ExperienceVersion, listNamesExperience(c.SectionVersions.Experience)); err != nil {
		return err
	}
	if err := missing("projects", c.Composition.ProjectsVersion, listNamesProjects(c.SectionVersions.Projects)); err != nil {
		return err
	}
	if err := missing("education", c.Composition.EducationVersion, listNamesEducation(c.SectionVersions.Education)); err != nil {
		return err
	}
	return nil
}

func validateRequiredFields(experience ExperienceVersion, projects ProjectsVersion, education EducationVersion) error {
	for i, e := range experience.Items {
		if strings.TrimSpace(e.Company) == "" || strings.TrimSpace(e.Role) == "" || strings.TrimSpace(e.DateRange) == "" {
			return fmt.Errorf("experience item %d must include company, role, and dateRange", i)
		}
	}
	for i, p := range projects.Items {
		if strings.TrimSpace(p.Name) == "" {
			return fmt.Errorf("project item %d must include name", i)
		}
	}
	for i, e := range education.Items {
		if strings.TrimSpace(e.Institution) == "" || strings.TrimSpace(e.Program) == "" || strings.TrimSpace(e.DateRange) == "" {
			return fmt.Errorf("education item %d must include institution, program, and dateRange", i)
		}
	}
	return nil
}

func mapSkills(v []SkillsVersion) map[string]SkillsVersion {
	out := make(map[string]SkillsVersion, len(v))
	for _, x := range v {
		out[x.Name] = x
	}
	return out
}

func mapExperience(v []ExperienceVersion) map[string]ExperienceVersion {
	out := make(map[string]ExperienceVersion, len(v))
	for _, x := range v {
		out[x.Name] = x
	}
	return out
}

func mapProjects(v []ProjectsVersion) map[string]ProjectsVersion {
	out := make(map[string]ProjectsVersion, len(v))
	for _, x := range v {
		out[x.Name] = x
	}
	return out
}

func mapEducation(v []EducationVersion) map[string]EducationVersion {
	out := make(map[string]EducationVersion, len(v))
	for _, x := range v {
		out[x.Name] = x
	}
	return out
}

func listNamesSkills(v []SkillsVersion) []string {
	out := make([]string, 0, len(v))
	for _, x := range v {
		out = append(out, x.Name)
	}
	return out
}

func listNamesExperience(v []ExperienceVersion) []string {
	out := make([]string, 0, len(v))
	for _, x := range v {
		out = append(out, x.Name)
	}
	return out
}

func listNamesProjects(v []ProjectsVersion) []string {
	out := make([]string, 0, len(v))
	for _, x := range v {
		out = append(out, x.Name)
	}
	return out
}

func listNamesEducation(v []EducationVersion) []string {
	out := make([]string, 0, len(v))
	for _, x := range v {
		out = append(out, x.Name)
	}
	return out
}

var errLatexEscapeInput = errors.New("latexEscape input must be string")
