<script setup>
    import { ref, watch } from 'vue'
    import dayjs from 'dayjs'
    import attestTyper from '@/assets/attestTypes.json'

    import Content from '@/components/Content.vue'
    import IconTable from '@/components/icons/IconTable.vue'

    import {
        getOrders,
        markOrderAsOrderedEndpoint,
        rejectOrderEndpoint
    } from '@/backendService'

    const props = defineProps({
        attestTypes: {
            type: Array,
            required: true
        }
    })  /* attestTypes array: [attestType, attestSubType] */
    
    // Events

    const emit = defineEmits(['updateOrderCount', 'updateOrdersCount', 'setOrderCount'])

    /*const callUpdate = () => {
        emit('updateOrderCount')
    }*/
    const callUpdateOrders = () => {
        emit('updateOrdersCount')
    }
    const callSetCount = (count) => {
        emit('setOrderCount', count)
    }

    // Initialization

    const orders = ref([])
    var flowStep = ref(0)

    const attestType = ref(props.attestTypes[0])
    const attestSubType = ref(props.attestTypes[1])

    // Set text
    const header = ref(attestTyper.find(x => x.typeId == attestType.value && x.subTypeId == attestSubType.value).name)
    const description = ref(attestTyper.find(x => x.typeId == attestType.value && x.subTypeId == attestSubType.value).longDescription)
    const url = ref(attestTyper.find(x => x.typeId == attestType.value).url)

    watch( () => props.attestTypes, (current, previous) => {
        // Update on change type
        attestType.value = current[0]
        attestSubType.value = current[1]
        fetchOrders()
    })

    fetchOrders()

    // Fetch orders

    function fetchOrders()
    {
        // Set text
        header.value = attestTyper.find(x => x.typeId == attestType.value && x.subTypeId == attestSubType.value).name
        description.value = attestTyper.find(x => x.typeId == attestType.value && x.subTypeId == attestSubType.value).longDescription
        url.value = attestTyper.find(x => x.typeId == attestType.value).url

        // Reset state
        flowStep.value = 0

        // Retrieve orders for type+subtype
        getOrders(attestType.value, attestSubType.value)
            .then(value => orders.value = value)
    }

    // Functions
    // Notification
    const notification = ref(null)

    function ordersProcessedNotification( count, isRejected = false )
    {
        if (isRejected)
            return {
                "message": " Attestrekvisitionen er blevet afvist. Rekvirent er blevet notificeret på mail.",
                "title": "Attestrekvisition afvist"
            }

        var attesterne = count > 1 ? "Attesterne" : "Attesten"
        var attester = count > 1 ? "attester" : "attest"

        return {
            "message": attesterne + " er blevet markeret som bestilt i systemet. Vær opmærksom på, at det er dit ansvar at " + attesterne.toLowerCase() + " er blevet bestilt korrekt. Status på igangværende bestillinger kan findes under Historik.",
            "title": count + " " + attester + " markeret som bestilt"
        }
    }

    // Flow

    function copyOrderList()
    {
        // Set flow step
        flowStep.value = 1

        // Join CPR to string
        var text = ""
        orders.value.forEach(element => {
            text += element.cpr + " " + element.navn + "\n"
        })
        
        // Then copy string to clipboard
        navigator.clipboard.writeText(text)
    }

    function openPolitiWebsite(skip = false)
    {
        // Set flow step
        flowStep.value = 2

        if(!skip)
            window.open(url.value, "_blank")
    }

    // Back-end interactions 

    function setAsOrdered()
    {
        // Reset flow step
        flowStep.value = 0

        // Obtain all ids from list
        var idList = []
        orders.value.forEach(element => {
            idList.push( element.orderId )
        })
        
        var idCount = idList.length

        // Perform POST request to backend
        markOrderAsOrderedEndpoint(idList)
            .then(response => {
                if (
                    response.success !== true
                    || !Number.isInteger(response.updated_count)
                    || response.updated_count < 0
                    || response.updated_count > idCount
                ) {
                    window.alert("Bestillingerne kunne ikke markeres som bestilt.")
                    return
                }

                const updatedCount = response.updated_count

                callUpdateOrders()
                fetchOrders()

                if (updatedCount === 0) {
                    window.alert("Ingen bestillinger blev opdateret. De kan allerede være behandlet.")
                    return
                }

                callSetCount(-updatedCount)
                notification.value=ordersProcessedNotification(updatedCount)
            })
            .catch(() => {
                window.alert("Bestillingerne kunne ikke gemmes. Prøv igen.")
            })
    }

    // Reject order

    const isRejectingOrder = ref(false)
    const rejectionReason = ref("")
    const reasonDescription = {
        "incorrect": "Fejl i CPR-nummer. CPR-nummeret findes ikke i CPR-registeret. Kontroller CPR-nummeret og prøv at bestille attesten igen.",
        "duplicate": "Duplikat bestilling. Bestillingen er en duplikat af en anden bestilling. Kontroller bestillingerne og prøv evt. at bestille attesten igen, hvis du mener der er tale om en fejl.",
        "other": ""
    }

    function reject(item)
    {
        // Perform POST request to backend
        rejectOrderEndpoint(
            item.orderId,
            rejectionReason.value,
            reasonDescription[rejectionReason.value]
        ).then((response) => {
            if (response.success !== true) {
                window.alert("Ordren blev ikke afvist. Den kan allerede være behandlet.")
                return
            }

            orders.value = orders.value.filter(order => order !== item)
            callSetCount(-1)
            callUpdateOrders()

            isRejectingOrder.value = false
            rejectionReason.value = ""
            reasonDescription["other"] = ""
            notification.value = ordersProcessedNotification(1, true)
    }).catch(() => {
        window.alert("Afvisningen kunne ikke gemmes. Prøv igen.")
    })
    }

</script>

<template>

    <div v-if="notification" class="message green" id="msg" style="margin-bottom: 2rem;">
        <div class="header">
            {{ notification.title }}
            <span class="float-right close" @click="notification = null">x</span>
        </div>
        {{ notification.message }}
    </div>

    <Content>
        <template #icon>
            <IconTable />
        </template>
        <template #heading>{{ header }}</template>

        <span class="paragraph">{{ description }}</span>

        <div class="paragraph">
            <table>
                <thead>
                    <tr>
                        <th>Dato <div class="text-small">Anmodet</div></th>
                        <th>Rekvirent <div class="text-small">Navn og email-adresse</div></th>
                        <th>Rekvisitus <div class="text-small">CPR-nummer</div></th>
                        <th></th>
                    </tr>
                </thead>
                
                <tr v-if="orders.length > 0" v-for="order in orders">
                    <td>{{ dayjs(order.requestedAt).format("DD-MM-YYYY") }}</td>
                    <td>{{ order.requesterName }}<div class="text-small">{{ order.requesterEmail }}</div></td>
                    <td>{{ order.cpr }}</td>
                    <td><button class="red" @click="isRejectingOrder = order">Afvis</button></td>
                </tr>
                <tr v-else>
                    <td colspan="4">Der er ingen bestillinger at vise.</td>
                </tr>

            </table>
        </div>

    </Content>

    <Content v-if="orders.length > 0">
        <template #icon>

        </template>
        <template #heading>Bestil attester</template>

        <span class="paragraph">Følg nedenstående trin for at gennemføre bestilling af attesterne:</span>

        <div class="paragraph buttons">

            <button @click="copyOrderList()" :class="flowStep > 0 ? 'green' : ''">
                1) Kopier CPR-numre
            </button>

            <div>
                <button @click="openPolitiWebsite()"  :class="flowStep > 1 ? 'green' : ''" :disabled="flowStep < 1">
                    2) Bestil på Politiets hjemmeside
                </button>

                <div id="flow_2" :class="'center text-small' +  (flowStep != 1 ? ' displaynone' : '')">
                    <a @click="openPolitiWebsite(true)">Spring over</a>
                </div>
            </div>
            
            <button @click="setAsOrdered()" :disabled="flowStep < 2">
                3) Markér attester som bestilt
            </button>

        </div>
    </Content>

    <div v-if="isRejectingOrder" @click="isRejectingOrder = false" class="fadeBackground"></div>
        <div v-if="isRejectingOrder" class="afvisDialog">
            <div>Angiv årsag til afvisning</div>
            <select v-model="rejectionReason">
                <option disabled value="">Vælg årsag</option>
                <option value="incorrect">Fejl i CPR-nummer</option>
                <option value="duplicate">Duplikat bestilling</option>
                <option value="other">Andet</option>
            </select>
            <textarea :disabled="rejectionReason !== 'other'" v-model="reasonDescription[rejectionReason]" placeholder="Angiv en årsag til afvisningen ..."></textarea>
            <button class="float-right red" @click="reject(isRejectingOrder)">Send afvisning</button>
    </div>
    

</template>

<style scoped>
    td:not(:first-child, :last-child)
    {
        padding-left: 1rem;
        padding-right: 1rem;
    }
    td:first-child
    {
        padding-right: 1rem;
    }
    td:last-child
    {
        padding-left: 1rem;
    }
    td[colspan="4"]
    {
        padding-right: 0rem;
        padding-left: 0rem;
    }
    .message
    {
        margin-top: 1rem;
        color: var(--color-white)
    }

    .buttons
    {
        display: flex;
    }
    .buttons > :not(:last-child)
    {
        margin-right: 1rem;
    }
    
    a:hover
    {
        cursor:pointer;
    }
    .text-small
    {
        font-size: 0.6em;
        text-transform: uppercase;
        color: var(--color-border-dark);
    }
    .displaynone
    {
        display: none;
    }

    .anim
    {
        transition: 300ms;
        transform: scaleY(1);
        opacity: 1;
    }
    .hidden
    {
        max-height: 0rem;
        transform: scaleY(0) translateY(-60%);
        opacity: 0;
        overflow: hidden;
    }
    .fadeBackground {
        background-color: rgba(0, 0, 0, 0.3);
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 1000;
        transform: translateY(-2rem);
    }
    .afvisDialog
    {
        z-index: 1001;
        position: absolute;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
        width: 45rem;
        background-color: var(--color-bg-light);
        border: 0.1rem solid;
        border-color: var(--color-red);
        border-radius: 0.5rem;
        padding: 1.5rem;
    }
        .afvisDialog > div
        {
            font-size: 1em;
            margin-bottom: 1rem;
        }
        .afvisDialog > *:last-child
        {
            margin-bottom: 0;
        }
        .afvisDialog > textarea
        {
            height: 10rem;
            resize: vertical;
        }
</style>