import { createRouter, createWebHistory } from 'vue-router'

const Home = () => import('@/views/Home.vue')
const Dashboard = () => import('@/views/Dashboard.vue')
const DatasetManagement = () => import('@/views/dataset/DatasetManagement.vue')
const DatasetDetail = () => import('@/views/dataset/DatasetDetail.vue')
const ModelProjects = () => import('@/views/models/ModelProjects.vue')
const ModelProjectDetail = () => import('@/views/models/ModelProjectDetail.vue')
const DetectObjects = () => import('@/views/mainfun/DetectObjects.vue')
const History = () => import('@/views/history/History.vue')
const NotFound = () => import('@/views/NotFound.vue')

const routes = [
  { path: '/', redirect: '/dashboard' },
  {
    path: '/home',
    name: 'Home',
    component: Home,
    children: [
      { path: '/dashboard', name: 'Dashboard', component: Dashboard },
      { path: '/dataset-management', name: 'DatasetManagement', component: DatasetManagement },
      { path: '/dataset-management/:id', name: 'DatasetDetail', component: DatasetDetail },
      { path: '/model-ranking', name: 'ModelProjects', component: ModelProjects },
      { path: '/model-ranking/:id', name: 'ModelProjectDetail', component: ModelProjectDetail },
      { path: '/detectobjects', name: 'Detectobjects', component: DetectObjects },
      { path: '/history', name: 'history', component: History }
    ]
  },
  { path: '/:pathMatch(.*)*', name: 'notfound', component: NotFound }
]

export default createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})
