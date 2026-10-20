import axios from "axios"

const api = axios.create({baseURL: '/api'})


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