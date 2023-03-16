/* eslint-disable jsx-a11y/label-has-associated-control */
/* eslint-disable camelcase */
/* eslint-disable no-shadow */
import React, { useState } from "react";
import { PlusOutlined, CloseOutlined, LeftOutlined } from "@ant-design/icons";
import { Button } from "antd";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "react-toastify";
import useToggleSlideOver from "../../stores/useToggleSlideOver";
import SlideOverCard from "./SlideOverCard";
import Select from "../base/Select/Select";
import { CurrencyType } from "../../types/pricing-unit-type";
import { Organization, PricingUnits } from "../../api/api";
import { ErrorResponseMessage } from "../../types/error-response-types";

const SlideOver: React.FC = () => {
  const open = useToggleSlideOver((state) => state.open);
  const setOpen = useToggleSlideOver((state) => state.setOpen);
  const [isCreating, setIsCreating] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [orgType, setOrgType] = useState("development");
  const [currencyCode, setCurrencyCode] = useState("USD");
  const queryClient = useQueryClient();
  const { data: pricingUnits }: UseQueryResult<CurrencyType[]> = useQuery<
    CurrencyType[]
  >(["pricing_unit_list"], () => PricingUnits.list().then((res) => res));
  const createOrgMutation = useMutation(
    ({
      organization_name,
      default_currency_code,
      organization_type,
    }: {
      organization_name: string;
      default_currency_code: string;
      organization_type: "development" | "production";
    }) =>
      Organization.createOrg(
        organization_name,
        default_currency_code,
        organization_type
      ),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["organization"]);
        setIsCreating(false);
        toast.success("Successfully created new environment");
      },
      onError: (error: ErrorResponseMessage) => {
        toast.error(error.response.data.detail);
      },
    }
  );
  const switchOrgMutation = useMutation(
    (org_id: string) => Organization.switchOrg(org_id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries();
        toast.success("Successfully switched environment");
      },
      onError: (error: ErrorResponseMessage) => {
        toast.error(error.response.data.detail);
      },
    }
  );
  const switchOrgHandler = (org_id: string) => {
    switchOrgMutation.mutate(org_id);
  };
  const submitHandler = () => {
    const variables = {
      organization_name: orgName,
      default_currency_code: currencyCode,
      organization_type: orgType as "development" | "production",
    };

    createOrgMutation.mutate(variables);
  };
  return (
    <div
      className={open ? "relative z-20" : "relative z-20 sr-only"}
      aria-labelledby="slide-over-title"
      role="dialog"
      aria-modal="true"
    >
      <div className="fixed inset-0" />
      <div className="fixed inset-0 overflow-hidden">
        <div className="absolute inset-0  overflow-hidden">
          <div
            className={
              open
                ? "pointer-events-none fixed inset-y-0 right-[0px] flex max-w-full"
                : "pointer-events-none fixed inset-y-0 right-[0px] flex max-w-full sr-only"
            }
          >
            <div className="pointer-events-auto w-screen h-screen max-w-md">
              <div className="flex h-full flex-col overflow-y-scroll bg-white py-6 shadow-xl">
                <div className="px-4 sm:px-6">
                  {!isCreating ? (
                    <div className="flex items-baseline mt-4">
                      <h2
                        className="text-lg font-medium text-gray-900 font-arimo"
                        id="slide-over-title"
                      >
                        Account Environments
                      </h2>
                      <div className="ml-auto flex flex-row  items-center ">
                        <PlusOutlined
                          onClick={() => setIsCreating(true)}
                          className="!text-gold w-12 h-12 cursor-pointer"
                        />
                        <CloseOutlined
                          onClick={() => setOpen()}
                          className="w-12 h-12 cursor-pointer"
                        />
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div className="flex items-baseline mt-4">
                        <div className="flex items-baseline gap-8">
                          <LeftOutlined
                            className="text-[12px] cursor-pointer"
                            onClick={() => setIsCreating(false)}
                          />
                          <h2
                            className="text-[20px] font-medium text-gray-900 font-arimo"
                            id="slide-over-title"
                          >
                            Create environment
                          </h2>
                        </div>
                        <div className="ml-auto flex flex-row  items-center ">
                          <CloseOutlined
                            onClick={() => setOpen()}
                            className="w-12 h-12 cursor-pointer"
                          />
                        </div>
                      </div>
                      <span className="text-card-grey text-base leading-4 Inter">
                        Create a new organization environment
                      </span>
                      <div className=" w-full h-[1.5px] mt-2 bg-card-divider" />
                    </div>
                  )}
                  {!isCreating && (
                    <div className=" w-full h-[1.5px] mt-2 bg-card-divider" />
                  )}
                </div>
                <div className="relative mt-6 flex-1 px-4 sm:px-6">
                  {/* replace w your content */}
                  {!isCreating ? (
                    <SlideOverCard switchOrg={switchOrgHandler} />
                  ) : (
                    <div className="flex flex-col gap-6">
                      <div>
                        <label
                          htmlFor="organization_name"
                          className="block text-sm font-medium text-[#9E9E9E]"
                        >
                          Name*
                        </label>
                        <div className="mt-1">
                          <input
                            type="text"
                            name="organization_name"
                            id="organization_name"
                            onChange={(e) => setOrgName(e.target.value)}
                            className="block w-[90%] rounded-md  text-[#9E9E9E] p-6 bg-gold-100 outline-none  shadow-sm  sm:text-sm"
                            placeholder="Enter name here..."
                          />
                        </div>
                      </div>
                      <Select>
                        <Select.Label className="text-[#9E9E9E] mb-2">
                          Type*
                        </Select.Label>
                        <Select.Select
                          onChange={(e) =>
                            setOrgType(e.target.value.toLowerCase())
                          }
                          className="bg-gold-100 text-[#9E9E9E] !w-[90%]"
                        >
                          <Select.Option selected>Development</Select.Option>
                          {["Production"].map((opt) => (
                            <Select.Option key={opt}>{opt}</Select.Option>
                          ))}
                        </Select.Select>
                      </Select>

                      <Select>
                        <Select.Label className="text-[#9E9E9E] mb-2">
                          Currency
                        </Select.Label>
                        <Select.Select
                          onChange={(e) => setCurrencyCode(e.target.value)}
                          className="bg-gold-100 text-[#9e9e9e] !w-[90%]"
                        >
                          <Select.Option selected>
                            Select an option
                          </Select.Option>
                          {pricingUnits?.map((pc) => (
                            <Select.Option key={pc.code}>
                              {pc.code}
                            </Select.Option>
                          ))}
                        </Select.Select>
                      </Select>
                      <Button
                        onClick={submitHandler}
                        type="primary"
                        size="large"
                        className="hover:!bg-primary-700"
                        key="create-org"
                        style={{
                          background: "#C3986B",
                          borderColor: "#C3986B",
                          width: "20%",
                        }}
                      >
                        <div className="flex items-center justify-between text-white">
                          <div>Create</div>
                        </div>
                      </Button>
                    </div>
                  )}
                  <div className="absolute inset-0 px-4 sm:px-6">
                    <div
                      className="h-full border-2 border-dashed border-gray-200"
                      aria-hidden="true"
                    />
                  </div>
                  {/* end replace */}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SlideOver;
