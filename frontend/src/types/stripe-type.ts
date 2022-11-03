export interface StripeImportCustomerResponse {
    status: string,
    detail: string,
}

export interface Source {
    source: string
}

export interface TransferSub extends Source{
    end_now: boolean
}
