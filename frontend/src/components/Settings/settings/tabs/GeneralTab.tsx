/* eslint-disable camelcase */
/* eslint-disable jsx-a11y/label-has-associated-control */
/* eslint-disable no-shadow */
import React, { FC, useEffect, useState } from "react";
import {
  useMutation,
  useQuery,
  UseQueryResult,
  useQueryClient,
} from "react-query";
import {
  Divider,
  Typography,
  Form,
  Input,
  Button,
  Modal,
  Select,
  Tag,
} from "antd";
import { toast } from "react-toastify";
import { PlusOutlined } from "@ant-design/icons";
import { Organization, PricingUnits } from "../../../../api/api";
import { CurrencyType } from "../../../../types/pricing-unit-type";
import LoadingSpinner from "../../../LoadingSpinner";
import useGlobalStore from "../../../../stores/useGlobalstore";
import { QueryErrors } from "../../../../types/error-response-types";
import { OrganizationType } from "../../../../types/account-type";
import country_json from "../../../../assets/country_codes";

const GeneralTab: FC = () => {
  const [isEdit, setIsEdit] = useState(false);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const org = useGlobalStore((state) => state.org);
  const [taxRate, setTaxRate] = useState(0);
  const [invoiceGracePeriod, setInvoiceGracePeriod] = useState(0);
  const [displayTaxRate, setDisplayTaxRate] = useState(0);
  const [displayInvoiceGracePeriod, setDisplayInvoiceGracePeriod] = useState(0);
  const [subscriptionFilters, setSubscriptionFilters] = useState<string[]>([]);
  const [newSubscriptionFilter, setNewSubscriptionFilter] =
    useState<string>("");

  const [line1, setLine1] = React.useState("");
  const [line2, setLine2] = React.useState("");
  const [city, setCity] = React.useState("");
  const [state, setState] = React.useState("");
  const [country, setCountry] = React.useState("");
  const [postalCode, setPostalCode] = React.useState("");
  const [currentCurrency, setCurrentCurrency] = useState("");
  const [formSubscriptionFilters, setFormSubscriptionFilters] =
    React.useState<string[]>(subscriptionFilters);

  const { data: pricingUnits }: UseQueryResult<CurrencyType[]> = useQuery<
    CurrencyType[]
  >(["pricing_unit_list"], () => PricingUnits.list().then((res) => res));

  const { data: orgData, isLoading } = useQuery(
    ["organization"],
    () => Organization.get().then((res) => res[0]),
    {}
  );

  useEffect(() => {
    if (orgData !== undefined) {
      if (
        orgData.default_currency !== undefined &&
        orgData.default_currency !== null
      ) {
        setCurrentCurrency(orgData.default_currency.code);
      }
      if (orgData.tax_rate === null) {
        setTaxRate(0);
        setDisplayTaxRate(0);
      } else {
        setTaxRate(orgData.tax_rate);
        setDisplayTaxRate(orgData.tax_rate);
      }
      if (orgData.payment_grace_period === null) {
        setInvoiceGracePeriod(0);
        setDisplayInvoiceGracePeriod(0);
      } else {
        setInvoiceGracePeriod(orgData.payment_grace_period);
        setDisplayInvoiceGracePeriod(orgData.payment_grace_period);
      }

      if (
        orgData.default_currency !== undefined &&
        orgData.default_currency !== null
      ) {
        setCurrentCurrency(orgData.default_currency.code);
      }

      setLine1(orgData.address ? orgData.address.line1 : "");
      setLine2(
        orgData.address && orgData.address.line2 ? orgData.address.line2 : ""
      );
      setCity(orgData.address ? orgData.address.city : "");
      setState(orgData.address ? orgData.address.state : "");
      setCountry(orgData.address ? orgData.address.country : "");
      setPostalCode(orgData.address ? orgData.address.postal_code : "");
      setSubscriptionFilters(orgData.subscription_filter_keys);
      setFormSubscriptionFilters(orgData.subscription_filter_keys);
    }
  }, [orgData]);

  const mutation = useMutation(
    (data: { email: string }) => Organization.invite(data.email),
    {
      onSuccess: () => {
        toast.success("Invite sent");
      },
      onError: (error: QueryErrors) => {
        if (error.response.data) {
          toast.error(
            Array.isArray(error.response.data.email)
              ? error.response.data.email[0]
              : error.response.data.email
          );
        } else {
          toast.error("Cannot send an invite now, try again later.");
        }
      },
    }
  );

  const updateOrg = useMutation(
    (obj: {
      org_id: string;
      default_currency_code: string;
      address: OrganizationType["address"];
      tax_rate: number;
      payment_grace_period: number;
      subscription_filter_keys: string[];
    }) =>
      Organization.updateOrganization(
        obj.org_id,
        obj.default_currency_code,
        obj.tax_rate,
        obj.payment_grace_period,
        obj.address,
        obj.subscription_filter_keys
      ),
    {
      onSuccess: () => {
        setIsEdit(false);

        toast.success("Successfully Updated Organization Settings", {
          position: toast.POSITION.TOP_CENTER,
        });
        queryClient.invalidateQueries(["organization"]);
        form.resetFields();
      },
      onError: () => {
        toast.error("Failed to Update Organization Settings", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const fourDP = (taxRate: number) =>
    parseFloat(parseFloat(String(taxRate)).toFixed(4));
  return (
    <div>
      <div className="flex justify-between w-6/12">
        <Typography.Title level={2}>Environment Settings</Typography.Title>
        <Button onClick={() => setIsEdit(true)} className="justify-self-end">
          Edit
        </Button>
      </div>

      <Divider />

      {isLoading ? (
        <div className="mt-10">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="flex flex-col w-6/12 justify-between">
          {mutation.isLoading && <LoadingSpinner />}
          <p className=" text-[16px]">
            <b>Company Name:</b> {org.organization_name}
          </p>
          <p className=" text-[16px]">
            <b className="">Default Organization Currency:</b>{" "}
            {org.default_currency !== undefined &&
            org.default_currency !== null ? (
              <Tag>
                {`${org.default_currency?.name} ${org.default_currency?.symbol}`}
              </Tag>
            ) : (
              "N/A"
            )}
          </p>
          <p className="text-[16px] space-y-2">
            <b>Billing address:</b> <p>{line1.length ? line1 : "Address"}</p>
            <p>{city.length ? city : "City State"}</p>
            <p>
              {country.length ? country : "Country"}{" "}
              {postalCode.length ? postalCode : "Zip"}
            </p>
          </p>
          <p className="text-[16px]">
            <b>Payment Grace Period:</b> {displayInvoiceGracePeriod}{" "}
            {displayInvoiceGracePeriod === 1 ? "day" : "days"}
          </p>
          {displayTaxRate !== null && displayTaxRate !== undefined ? (
            <p className="text-[16px]">
              <b>Organization Tax Rate:</b> {displayTaxRate} %
            </p>
          ) : (
            <p className="text-[16px]">
              <b>Organization Tax Rate:</b> None
            </p>
          )}
          <p className="text-[16px]">
            <b>Subscription Filters:</b>{" "}
            {orgData?.subscription_filter_keys.map((filter) => (
              <Tag key={filter}>{filter}</Tag>
            ))}
          </p>

          <div className=" flex justify-end" />
        </div>
      )}
      <Modal
        title="Edit Organization Settings"
        visible={isEdit}
        onCancel={() => setIsEdit(false)}
        okText="Save"
        onOk={() => {
          if (org.organization_id.length) {
            let submittedAddress;
            if (
              city === "" &&
              line1 === "" &&
              country === "" &&
              postalCode === "" &&
              state === "" &&
              line2 === ""
            ) {
              submittedAddress = null;
            } else {
              submittedAddress = {
                city,
                line1,
                line2,
                country,
                postal_code: postalCode,
                state,
              };
            }
            updateOrg.mutate({
              org_id: org.organization_id,
              default_currency_code: currentCurrency,
              tax_rate: fourDP(taxRate),
              payment_grace_period: invoiceGracePeriod,
              address: submittedAddress,
              subscription_filter_keys: subscriptionFilters,
            });
          }
        }}
      >
        <div className="flex flex-col justify-between">
          <Form
            form={form}
            initialValues={{
              organization_name: org?.organization_name,
              default_currency: org?.default_currency?.code,
            }}
          >
            <Form.Item
              label="Company Name"
              name="organization_name"
              rules={[
                {
                  required: true,
                },
              ]}
            >
              <Input disabled />
            </Form.Item>
            <Form.Item
              label="Default Organization Currency"
              name="default_currency"
            >
              <Select
                onChange={setCurrentCurrency}
                options={pricingUnits?.map((pc) => ({
                  label: `${pc.name} ${pc.symbol}`,
                  value: pc.code,
                }))}
              />
            </Form.Item>
            <Form.Item label="Tax Rate" name="tax_rate">
              <Input
                type="number"
                step=".01"
                max={999.9999}
                onChange={(e) =>
                  setTaxRate(e.target.value as unknown as number)
                }
                defaultValue={taxRate}
              />
            </Form.Item>
            <Form.Item name="billing_address">
              <label className="mb-2">Billing Address: </label>
              <div className="flex gap-4 mt-2">
                <Input
                  placeholder="Address Line 1"
                  defaultValue={line1}
                  onChange={(e) => setLine1(e.target.value)}
                  required
                />
                <Input
                  placeholder="Address Line 2"
                  defaultValue={line2}
                  onChange={(e) => setLine2(e.target.value)}
                />
              </div>
              <div className="flex gap-4 mt-2">
                <Input
                  placeholder="City"
                  onChange={(e) => setCity(e.target.value)}
                  defaultValue={city}
                  required
                />
                <Select
                  placeholder="Country"
                  defaultValue={country}
                  onChange={(e) => setCountry(e)}
                >
                  {country_json.map((country) => (
                    <Select.Option key={country.Code} value={country.Code}>
                      {country.Name}
                    </Select.Option>
                  ))}
                </Select>
              </div>
              <div className="flex gap-4 mt-2">
                <Input
                  placeholder="State"
                  defaultValue={state}
                  onChange={(e) => setState(e.target.value)}
                  required
                />
                <Input
                  defaultValue={postalCode}
                  placeholder="Zip Code"
                  onChange={(e) => setPostalCode(e.target.value)}
                  required
                />
              </div>
            </Form.Item>
            <Form.Item label="Payment Grace Period" name="payment_grace_period">
              <Input
                type="number"
                step="1"
                onChange={(e) => setInvoiceGracePeriod(Number(e.target.value))}
                defaultValue={invoiceGracePeriod}
              />
            </Form.Item>
            <Form.Item label="Subscription Filters" name="subscription_filters">
              <Select
                mode="multiple"
                value={subscriptionFilters.map((filter) => filter)}
                placeholder="Select subscription filters"
                onChange={(e) => setSubscriptionFilters(e)}
                optionLabelProp="label"
                options={formSubscriptionFilters.map((filter) => ({
                  label: filter,
                  value: filter,
                }))}
              />
            </Form.Item>

            <Input
              value={newSubscriptionFilter}
              placeholder="Enter New Subscription Filter"
              onChange={(e) => setNewSubscriptionFilter(e.target.value)}
            />
            <Button
              onClick={() => {
                if (newSubscriptionFilter.length !== 0) {
                  setFormSubscriptionFilters([
                    ...formSubscriptionFilters,
                    newSubscriptionFilter,
                  ]);

                  setNewSubscriptionFilter("");
                }
              }}
              type="primary"
              size="small"
              key="create-plan"
              className="hover:!bg-primary-700 mt-4 float-right py-4"
              style={{ background: "#C3986B", borderColor: "#C3986B" }}
            >
              <div className="flex items-center  justify-between text-white">
                <div>
                  <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
                  Create Filter
                </div>
              </div>
            </Button>
          </Form>
        </div>
      </Modal>
    </div>
  );
};

export default GeneralTab;
