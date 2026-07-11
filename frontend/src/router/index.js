import { createRouter, createWebHistory } from 'vue-router'

const Home = () => import('@/views/Home.vue')
const DetectObjects = () => import('@/views/mainfun/DetectObjects.vue')
const History = () => import('@/views/history/History.vue')
const NotFound = () => import('@/views/NotFound.vue')

const routes = [
  { path: '/', redirect: '/detectobjects' },
  {
    path: '/home',
    name: 'Home',
    component: Home,
    children: [
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
