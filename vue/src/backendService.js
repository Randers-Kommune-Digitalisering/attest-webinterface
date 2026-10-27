import axios from "axios"

const api = axios.create({baseURL: '/api'})

api.interceptors.response.use(
    response => response,
    error => {
        if (error.response?.status === 401) {
            window.location.href = '/api/login'
        }
        return Promise.reject(error)
    }
)


export const getAllOrders = () =>
    api.get(`/orders`)
        .then(response => response.data)


export const getOrders = (attest_type, sub_type) =>
    api.get(`/orders/${attest_type}/${sub_type}`)
        .then(response => response.data)


export const getOrderCount = () =>
    api.get(`/ordercount`)
        .then(response => response.data)


export const getOrderedHistory = () =>
    api.get(`/history/ordered`)
        .then(response => response.data)


export const getCompletedHistory = () =>
    api.get(`/history/completed`)
        .then(response => response.data)


export const rejectOrderEndpoint = (orderId, reason, description) =>
    api.post(`/rejectorder/${encodeURIComponent(orderId)}`, { reason, description })
        .then(response => response.data)


export const markOrderAsOrderedEndpoint = (orderIds) =>
    api.post(`/processorders`, orderIds)
        .then(response => response.data)


export const getExpressStatus = () =>
    axios.get('/status')
        .then(response => response.data)