// @ts-ignore
import React, { FC, useState } from "react";
import {
  useMutation,
  useQuery,
  UseQueryResult,
  useQueryClient,
} from "react-query";
import { useNavigate } from "react-router-dom";
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
import { Organization, PricingUnits } from "../../../../api/api";
import { PricingUnit } from "../../../../types/pricing-unit-type";
import { toast } from "react-toastify";
import LoadingSpinner from "../../../LoadingSpinner";
import useGlobalStore from "../../../../stores/useGlobalstore";
import { QueryErrors } from "../../../../types/error-response-types";
import { OrganizationType } from "../../../../types/account-type";
import { country_json } from "../../../../assets/country_codes";

interface InviteWithEmailForm extends HTMLFormControlsCollection {
  email: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: InviteWithEmailForm;
}

const GeneralTab: FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [isEdit, setIsEdit] = useState(false);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const org = useGlobalStore((state) => state.org);
  const [currentCurrency, setCurrentCurrency] = useState("");
  const [taxRate, setTaxRate] = useState(0);
  const [invoiceGracePeriod, setInvoiceGracePeriod] = useState(0);
  const [displayTaxRate, setDisplayTaxRate] = useState(0);
  const [displayInvoiceGracePeriod, setDisplayInvoiceGracePeriod] = useState(0);

  const [line1, setLine1] = React.useState("");
  const [line2, setLine2] = React.useState("");
  const [city, setCity] = React.useState("");
  const [state, setState] = React.useState("");
  const [country, setCountry] = React.useState("");
  const [postalCode, setPostalCode] = React.useState("");
  const {
    data: pricingUnits,
    isLoading: pricingUnitsLoading,
  }: UseQueryResult<PricingUnit[]> = useQuery<PricingUnit[]>(
    ["pricing_unit_list"],
    () =>
      PricingUnits.list().then((res) => {
        return res;
      })
  );

  const { isLoading } = useQuery(
    ["organization"],
    () =>
      Organization.get().then((res) => {
        //if the default currency is null, then don't set it, otherwise setCurrentCurrency
        if (
          res[0].default_currency !== undefined &&
          res[0].default_currency !== null
        ) {
          setCurrentCurrency(res[0].default_currency.code);
        }
        if (res[0].tax_rate === null) {
          setTaxRate(0);
          setDisplayTaxRate(0);
        } else {
          setTaxRate(res[0].tax_rate);
          setDisplayTaxRate(res[0].tax_rate);
        }
        if (res[0].invoice_grace_period === null) {
          setInvoiceGracePeriod(0);
          setDisplayInvoiceGracePeriod(0);
        } else {
          setInvoiceGracePeriod(res[0].invoice_grace_period);
          setDisplayInvoiceGracePeriod(res[0].invoice_grace_period);
        }

        return res[0];
      }),
    {
      onSuccess: (data) => {
        if (
          data.default_currency !== undefined &&
          data.default_currency !== null
        ) {
          setCurrentCurrency(data.default_currency.code);
        }

        setLine1(data.address ? data.address.line1 : "");
        setLine2(data.address && data.address.line2 ? data.address.line2 : "");
        setCity(data.address ? data.address.city : "");
        setState(data.address ? data.address.state : "");
        setCountry(data.address ? data.address.country : "");
        setPostalCode(data.address ? data.address.postal_code : "");
      },
    }
  );

  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  const mutation = useMutation(
    (data: { email: string }) => Organization.invite(email),
    {
      onSuccess: (response) => {
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
      invoice_grace_period: number;
    }) =>
      Organization.updateOrganization(
        obj.org_id,
        obj.default_currency_code,
        obj.tax_rate,
        obj.invoice_grace_period,
        obj.address
      ),
    {
      onSuccess: () => {
        toast.success("Successfully Updated Organization Settings", {
          position: toast.POSITION.TOP_CENTER,
        });
        queryClient.invalidateQueries("organization");
        setIsEdit(false);
        form.resetFields();
      },
      onError: () => {
        toast.error("Failed to Update Organization Settings", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const handleSendInviteEmail = (event: React.FormEvent<FormElements>) => {
    mutation.mutate({ email });
  };
  const fourDP = (taxRate: number) =>
    parseFloat(parseFloat(String(taxRate)).toFixed(4));
  return (
    <div>
      <div className="flex justify-between w-6/12">
        <Typography.Title level={2}>Organization Settings</Typography.Title>
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
            <b>Company Name:</b> {org.company_name}
          </p>
          <p className=" text-[16px]">
            <b className="">Default Organization Currency:</b>{" "}
            {org.default_currency !== undefined &&
            org.default_currency !== null ? (
              <Tag>
                {org.default_currency?.name +
                  " " +
                  org.default_currency?.symbol}
              </Tag>
            ) : (
              "N/A"
            )}
          </p>
          <p className="text-[16px] space-y-2">
            <b>Billing address:</b>{" "}
            <p>{line1.length ? line1 : "1292 Lane Place"}</p>
            <p>{city.length ? city : "Cambridge MA"}</p>
            <p>
              {country.length ? country : "USA"}{" "}
              {postalCode.length ? postalCode : "92342"}
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

          <div className=" flex justify-end"></div>
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
              invoice_grace_period: invoiceGracePeriod,
              address: submittedAddress,
            });
            // updateOrg.mutate({
            //   org_id: org.organization_id,
            //   default_currency_code: currentCurrency,
            //   tax_rate: fourDP(taxRate),
            //   invoice_grace_period: invoiceGracePeriod,
            // });
          }
        }}
      >
        <div className="flex flex-col justify-between">
          <Form
            form={form}
            initialValues={{
              company_name: org?.company_name,
              default_currency: org?.default_currency?.code,
            }}
          >
            <Form.Item
              label="Company Name"
              name="company_name"
              rules={[
                {
                  required: true,
                },
              ]}
            >
              <Input disabled={true} />
            </Form.Item>
            <Form.Item
              label="Default Organization Currency"
              name="default_currency"
            >
              <Select
                onChange={setCurrentCurrency}
                options={pricingUnits?.map((pc) => {
                  return { label: `${pc.name} ${pc.symbol}`, value: pc.code };
                })}
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
                    <Select.Option value={country.Code}>
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
            <Form.Item label="Payment Grace Period" name="invoice_grace_period">
              <Input
                type="number"
                step="1"
                onChange={(e) => setInvoiceGracePeriod(Number(e.target.value))}
                defaultValue={invoiceGracePeriod}
              />
            </Form.Item>
          </Form>
        </div>
      </Modal>
    </div>
  );
};

export default GeneralTab;
