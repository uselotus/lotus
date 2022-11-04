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

export interface OrganizationSettingsParams{
    setting_group: string
    setting_name?: string
}

export interface OrganizationSettings{
    setting_group: string
    setting_id: string
    setting_name: string
    setting_value: string
}

export interface UpdateOrganizationSettingsParams{
    setting_id: string
    setting_value: string
}
