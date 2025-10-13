import { create } from 'zustand';
import { Project } from '../types/Project';
import { Agent } from '../types/Agent';

interface ProjectStore {
  projects: Project[];
  selectedProject: Project | null;
  agents: Agent[];
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setProjects: (projects: Project[]) => void;
  setSelectedProject: (project: Project | null) => void;
  setAgents: (agents: Agent[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  addProject: (project: Project) => void;
  removeProject: (projectId: string) => void;
  updateProject: (projectId: string, updates: Partial<Project>) => void;
  toggleProjectFavorite: (projectId: string) => void;
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  selectedProject: null,
  agents: [],
  isLoading: false,
  error: null,

  setProjects: (projects) => set({ projects }),
  
  setSelectedProject: (project) => set({ selectedProject: project }),
  
  setAgents: (agents) => set({ agents }),
  
  setLoading: (loading) => set({ isLoading: loading }),
  
  setError: (error) => set({ error }),
  
  addProject: (project) => set((state) => ({
    projects: [...state.projects, project]
  })),
  
  removeProject: (projectId) => set((state) => ({
    projects: state.projects.filter(p => p.id !== projectId),
    selectedProject: state.selectedProject?.id === projectId ? null : state.selectedProject
  })),
  
  updateProject: (projectId, updates) => set((state) => ({
    projects: state.projects.map(p => 
      p.id === projectId ? { ...p, ...updates } : p
    ),
    selectedProject: state.selectedProject?.id === projectId 
      ? { ...state.selectedProject, ...updates }
      : state.selectedProject
  })),
  
  toggleProjectFavorite: (projectId) => set((state) => {
    const project = state.projects.find(p => p.id === projectId);
    if (!project) return state;
    
    const updatedProjects = state.projects.map(p =>
      p.id === projectId ? { ...p, favorite: !p.favorite } : p
    );
    
    return {
      projects: updatedProjects,
      selectedProject: state.selectedProject?.id === projectId
        ? { ...state.selectedProject, favorite: !state.selectedProject.favorite }
        : state.selectedProject
    };
  })
}));
